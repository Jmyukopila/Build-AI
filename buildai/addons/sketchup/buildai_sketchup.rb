# BuildAI Bridge para SketchUp
#
# Extensión que abre un pequeño servidor local (puerto 8602) para que BuildAI
# pueda consultar el modelo y ejecutar código Ruby dentro de SketchUp.
# Solo acepta conexiones desde este mismo ordenador (127.0.0.1).
#
# Compatible con SketchUp 8 en adelante (probado el camino moderno en 2014+;
# en versiones sin la librería 'json' se usa un mini JSON incluido aquí).
#
# Instalación: copiar este archivo a la carpeta Plugins de SketchUp (BuildAI
# lo hace solo con el botón "Conectar automáticamente"). Al reiniciar
# SketchUp, el puente se inicia automáticamente: no hay que tocar ningún menú.
# El menú Extensiones → BuildAI Bridge permite ver el estado o detenerlo.

require 'sketchup.rb'
require 'socket'
begin
  require 'thread' # necesario para Mutex en Rubys antiguos; inofensivo en modernos
rescue LoadError
end
begin
  require 'json'
rescue LoadError
end

module BuildAI
  PUERTO = 8602
  JSON_DISPONIBLE = defined?(JSON) ? true : false

  @cola = []            # [peticion, contenedor_respuesta]
  @mutex_cola = Mutex.new
  @servidor = nil
  @timer = nil

  # ---------- JSON mínimo (para SketchUp sin librería json) ----------

  ESCAPES_JSON = {
    '"' => '\"', '\\' => '\\\\', "\b" => '\b', "\f" => '\f',
    "\n" => '\n', "\r" => '\r', "\t" => '\t'
  }

  def self.a_json_texto(valor)
    return valor.to_s if valor == true || valor == false
    texto = valor.to_s.gsub(/["\\\x00-\x1f]/) do |c|
      ESCAPES_JSON[c] || format('\u%04x', c.unpack('C')[0])
    end
    '"' + texto + '"'
  end

  def self.a_json(hash)
    return JSON.generate(hash) if JSON_DISPONIBLE
    pares = hash.map { |k, v| a_json_texto(k.to_s) + ':' + a_json_texto(v) }
    '{' + pares.join(',') + '}'
  end

  def self.extraer_codigo(cuerpo)
    if JSON_DISPONIBLE
      return (JSON.parse(cuerpo)['codigo'] || '' rescue '')
    end
    m = cuerpo.match(/"codigo"\s*:\s*"((?:\\.|[^"\\])*)"/m)
    return '' unless m
    m[1].gsub(/\\(u[0-9a-fA-F]{4}|["\\\/bfnrt])/) do
      e = $1
      if e[0, 1] == 'u'
        [e[1, 4].to_i(16)].pack('U')
      else
        { '"' => '"', '\\' => '\\', '/' => '/', 'b' => "\b",
          'f' => "\f", 'n' => "\n", 'r' => "\r", 't' => "\t" }[e]
      end
    end
  end

  # ---------- Lógica del puente ----------

  def self.info_modelo
    modelo = Sketchup.active_model
    return 'No hay ningún modelo abierto en SketchUp.' unless modelo
    lineas = []
    lineas << "SketchUp #{Sketchup.version}"
    lineas << "Modelo: #{modelo.title.empty? ? '(sin guardar)' : modelo.title}"
    lineas << "Entidades en nivel raíz: #{modelo.entities.length}"
    lineas << "Definiciones de componente: #{modelo.definitions.length}"
    lineas << "Materiales: #{modelo.materials.map { |m| m.name }.join(', ')}"
    lineas << "Etiquetas/capas: #{modelo.layers.map { |c| c.name }.join(', ')}"
    lineas.join("\n")
  end

  # Se ejecuta SIEMPRE en el hilo principal de SketchUp
  def self.procesar(peticion)
    case peticion['accion']
    when 'ping'
      { 'ok' => true, 'resultado' => 'pong' }
    when 'info'
      { 'ok' => true, 'resultado' => info_modelo }
    when 'ejecutar'
      begin
        resultado = eval(peticion['codigo'].to_s, TOPLEVEL_BINDING) # rubocop:disable Security/Eval
        { 'ok' => true, 'resultado' => resultado.to_s[0, 12000] }
      rescue Exception => e
        { 'ok' => false, 'error' => "#{e.class}: #{e.message}\n#{e.backtrace ? e.backtrace.first(5).join("\n") : ''}" }
      end
    else
      { 'ok' => false, 'error' => 'Acción desconocida' }
    end
  end

  def self.bombear
    trabajo = @mutex_cola.synchronize { @cola.shift }
    return unless trabajo
    peticion, contenedor = trabajo
    contenedor[:respuesta] = begin
      procesar(peticion)
    rescue Exception => e
      { 'ok' => false, 'error' => e.message }
    end
  end

  def self.atender(cliente)
    cabecera = cliente.gets("\r\n\r\n")
    return cliente.close if cabecera.nil?

    ruta = cabecera.split(' ')[1].to_s
    longitud = cabecera[/Content-Length:\s*(\d+)/i, 1].to_i
    cuerpo = longitud > 0 ? cliente.read(longitud) : ''

    peticion =
      case ruta
      when '/ping'     then { 'accion' => 'ping' }
      when '/info'     then { 'accion' => 'info' }
      when '/ejecutar' then { 'accion' => 'ejecutar', 'codigo' => extraer_codigo(cuerpo) }
      else { 'accion' => 'desconocida' }
      end

    # Encolar para el hilo principal y esperar la respuesta (sondeo: funciona
    # en cualquier versión de Ruby, sin ConditionVariable con timeout)
    contenedor = {}
    @mutex_cola.synchronize { @cola << [peticion, contenedor] }
    limite = Time.now + 120
    sleep(0.05) until contenedor.key?(:respuesta) || Time.now > limite
    respuesta = contenedor[:respuesta] || { 'ok' => false, 'error' => 'Tiempo de espera agotado en SketchUp.' }

    cuerpo_json = a_json(respuesta)
    bytes = cuerpo_json.respond_to?(:bytesize) ? cuerpo_json.bytesize : cuerpo_json.length
    cliente.write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: #{bytes}\r\nConnection: close\r\n\r\n#{cuerpo_json}")
  rescue Exception
    # conexión rota: ignorar
  ensure
    cliente.close rescue nil
  end

  def self.iniciar(silencioso = false)
    if @servidor
      UI.messagebox('BuildAI Bridge ya está en marcha.') unless silencioso
      return
    end
    @servidor = TCPServer.new('127.0.0.1', PUERTO)
    Thread.new do
      loop do
        cliente = @servidor.accept rescue break
        Thread.new(cliente) { |c| atender(c) }
      end
    end
    @timer = UI.start_timer(0.15, true) { bombear }
    if silencioso
      Sketchup.status_text = "BuildAI Bridge activo (puerto #{PUERTO})" rescue nil
    else
      UI.messagebox("BuildAI Bridge iniciado ✔\nYa puedes usar SketchUp desde BuildAI.")
    end
  rescue Exception => e
    @servidor = nil
    # Puerto ocupado (¿otro SketchUp abierto?) u otro fallo
    if silencioso
      puts "[BuildAI] No se pudo iniciar el puente: #{e.message}"
    else
      UI.messagebox("No se pudo iniciar BuildAI Bridge: #{e.message}")
    end
  end

  def self.detener
    UI.stop_timer(@timer) if @timer
    @servidor.close rescue nil
    @servidor = nil
    @timer = nil
    UI.messagebox('BuildAI Bridge detenido.')
  end

  def self.estado
    if @servidor
      UI.messagebox("BuildAI Bridge está ACTIVO en el puerto #{PUERTO}.")
    else
      UI.messagebox('BuildAI Bridge está detenido. Usa "Iniciar" para arrancarlo.')
    end
  end

  unless file_loaded?(__FILE__)
    menu = UI.menu('Extensions').add_submenu('BuildAI Bridge')
    menu.add_item('Estado') { estado }
    menu.add_item('Iniciar') { iniciar }
    menu.add_item('Detener') { detener }
    # Auto-inicio: arranca solo al abrir SketchUp, sin pasos manuales
    UI.start_timer(1.0, false) { iniciar(true) }
    file_loaded(__FILE__)
  end
end
