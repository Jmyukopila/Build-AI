# 🏗️ BuildAI — Asistente de IA para arquitectos

BuildAI conecta una inteligencia artificial con **Revit, AutoCAD, SketchUp y
Blender** para que puedas trabajar hablando en tu idioma, sin saber programar:

> _"Crea una casa de una planta de 10×8 metros con cubierta a dos aguas"_
> _"Organízame las capas de este dibujo"_
> _"¿Qué hay en este modelo?"_

Todo se ejecuta **en tu ordenador**: tus claves y tus modelos no salen de él
(solo se envían los mensajes al proveedor de IA que elijas).

---

## 🚀 Puesta en marcha (5 minutos)

### 1. Instalar (solo la primera vez)

**Opción recomendada: instalador `BuildAI-Setup.exe`**

No necesitas tener Python instalado. Ejecuta `BuildAI-Setup.exe` y sigue el
asistente (dos clics, sin pedir permisos de administrador): instala BuildAI en
tu carpeta de usuario y crea accesos directos en el **Menú Inicio** y, si lo
marcas, en el **Escritorio** — igual que instalar cualquier otro programa.
Incluye un desinstalador normal en *Agregar o quitar programas*.

Si no tienes ya ese instalador, cualquiera con el código fuente puede
generarlo en un paso — ver [Generar el instalador](#-generar-el-instalador-buildai-setupexe).

**Alternativa: desde el código fuente (requiere Python)**
1. Instala [Python 3.11+](https://www.python.org/downloads/) marcando
   **"Add Python to PATH"**.
2. Haz doble clic en **`INSTALAR.bat`**.

Al terminar tendrás los puentes instalados en tus programas y un **acceso
directo "BuildAI" en el escritorio**.

> 💻 ¿Prefieres la terminal? También se instala con un solo comando desde
> GitHub: mira [Instalar desde terminal](#-instalar-desde-terminal-pip--pipx--uv).

### 2. Arrancar
Haz doble clic en el acceso directo **BuildAI** (Escritorio o Menú Inicio, o
`INICIAR.bat` si vienes del código fuente). Se abre una **ventana propia de la
aplicación** — como VS Code o Excel, no una pestaña del navegador — con la
interfaz servida internamente en `http://127.0.0.1:8600`.

### 3. Configurar la IA
Pulsa **⚙️ Ajustes de IA** y elige proveedor:

| Proveedor | Coste | Dónde sacar la clave |
|---|---|---|
| **OpenRouter** (recomendado para empezar) | Gratis (modelos `:free`) | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **Ollama** (IA local en tu PC) | Gratis, sin clave | Solo [instalar Ollama](https://ollama.com/download); BuildAI detecta tus modelos |
| Anthropic (Claude) | De pago | [platform.claude.com](https://platform.claude.com/) |
| OpenAI (GPT) | De pago | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| Google (Gemini) | Nivel gratuito | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |

> Al elegir proveedor en Ajustes, BuildAI te muestra la lista de modelos:
> los **gratuitos con soporte de herramientas** en OpenRouter (consultados en
> vivo) y tus **modelos locales** si usas Ollama. Para controlar los programas,
> el modelo debe saber usar herramientas (en Ollama: `qwen3`, `llama3.1+`, etc.).

> ℹ️ Estos proveedores no ofrecen inicio de sesión con cuenta (OAuth) para sus
> APIs: todos funcionan con una **clave de API** que se crea en un minuto con
> los enlaces de arriba. La clave se guarda solo en `config.json`, en tu equipo.

### 4. Conectar tus programas
`INSTALAR.bat` ya instala los puentes en todos los programas que detecte.
Si instalas un programa después (o algo falla), pulsa **❓** junto al programa
en la barra lateral y luego **⚡ Conectar automáticamente**:

| Programa | Qué hace falta | Versiones compatibles |
|---|---|---|
| 🟠 **Blender** | Nada: el puente se instala solo y arranca con Blender | 2.80 – 4.x |
| 🔴 **AutoCAD** | Nada: se conecta solo si AutoCAD está abierto | 2004+ (no LT) |
| 🔵 **SketchUp** | Nada: la extensión se instala y se inicia sola | 2014+ |
| 🟣 **Revit** | Solo instalar [pyRevit](https://github.com/pyrevitlabs/pyRevit/releases) (gratis); el resto es automático | 2014+ con pyRevit 4.8+ |

Después de conectar, **abre (o reinicia) el programa**. El punto de cada
programa se pone **verde** cuando está conectado.

> 📖 Guía detallada con solución de problemas: pulsa **Manual de conexión**
> en la barra lateral (o abre `http://127.0.0.1:8600/manual`).

### 5. ¡A trabajar!
Escribe lo que necesitas en el chat (Enter envía, Mayús+Enter hace salto de
línea) o pulsa una **tarea rápida** de la barra lateral. Verás en tiempo real
cuándo la IA está trabajando dentro de tus programas (🔧) y podrás desplegar
el detalle técnico si te interesa.

- **Historial**: cada conversación se guarda automáticamente en
  `~/.buildai/sesiones/` (tu carpeta de usuario). Desde el panel **Historial**
  de la barra lateral puedes retomarla donde la dejaste o borrarla.
- **Exportar**: el botón de descarga (arriba a la derecha) guarda la
  conversación como archivo Markdown, útil para documentar un proyecto.
- **Copiar**: al pasar el ratón por una respuesta aparece un botón para
  copiarla entera.

---

## 📦 Instalar desde terminal (pip / pipx / uv)

BuildAI es un paquete de Python: se instala directamente desde GitHub sin
descargar nada a mano.

### Con pipx o uv (recomendado: aislado y sin líos)

[pipx](https://pipx.pypa.io/) y [uv](https://docs.astral.sh/uv/) instalan la
aplicación en su propio entorno aislado, como hace `npx`/`npm -g` en Node:

```bat
:: con pipx  (pip install pipx, una sola vez)
pipx install git+https://github.com/Jmyukopila/Build-AI.git
buildai-instalar   :: instala los puentes y el acceso directo del escritorio
buildai            :: arranca y abre la ventana de la app

:: o con uv, incluso sin instalar nada (equivalente a npx):
uvx --from git+https://github.com/Jmyukopila/Build-AI.git buildai
```

### Con pip clásico

Recomendado: dentro de un **entorno virtual** en una carpeta normal
(Escritorio, Documentos…), no con `pip install --user`.

```bat
:: 1. Crear y activar un entorno virtual (una sola vez)
python -m venv %USERPROFILE%\buildai-env
%USERPROFILE%\buildai-env\Scripts\activate

:: 2. Instalar BuildAI desde GitHub (o "pip install ." desde la carpeta del
::    proyecto, o desde un .whl que te pasen)
pip install git+https://github.com/Jmyukopila/Build-AI.git

:: 3. Instalar los puentes en los programas detectados
buildai-instalar

:: 4. Arrancar (abre la ventana de la app)
buildai
```

A partir de ahí, cualquier terminal con ese entorno virtual activado tiene los
comandos `buildai` (arranca el servidor y abre el navegador) y
`buildai-instalar` (busca Blender/AutoCAD/SketchUp/Revit y reinstala los
puentes). La configuración y el historial de cada persona se guardan en su
propia carpeta `~/.buildai`, así que varios usuarios pueden instalarlo en el
mismo equipo sin pisarse la configuración.

> ⚠️ Si en tu equipo `python` resuelve al Python de **Microsoft Store**, evita
> `pip install --user`: esa combinación guarda los archivos en una carpeta de
> AppData que ese Python virtualiza (el propio programa la ve, pero programas
> reales como Blender no reciben el archivo copiado). Un entorno virtual como
> el de arriba evita el problema por completo. Si BuildAI detecta este caso
> igualmente, te avisará por consola al arrancar o al ejecutar
> `buildai-instalar`.

Para generar un `.whl` distribuible a otra persona (no necesita el código
fuente, solo Python 3.11+):

```bat
pip install build
python -m build --wheel
:: genera dist\buildai-0.1.0-py3-none-any.whl — se instala con "pip install <archivo>.whl"
```

---

## 🏗️ Generar el instalador (`BuildAI-Setup.exe`)

Para producir el instalador de escritorio (el de la opción recomendada más
arriba) a partir del código fuente, en Windows con
[Inno Setup](https://jrsoftware.org/isinfo.php) instalado
(`winget install JRSoftware.InnoSetup`):

```powershell
powershell -File build_installer.ps1
```

El script crea (o reutiliza) un entorno virtual `.venv`, empaqueta la app con
PyInstaller en `build_pkg\dist\BuildAI\` y compila el instalador con Inno
Setup. El resultado queda en **`build_pkg\Output\BuildAI-Setup.exe`**, listo
para repartir: instala sin pedir administrador, en `%LOCALAPPDATA%\Programs\BuildAI`,
con accesos directos y desinstalador.

Piezas del empaquetado, por si necesitas tocarlas:

| Archivo | Qué hace |
|---|---|
| `build_pkg/run_buildai.py` | Punto de entrada que llama a `buildai.main.arrancar()` |
| `build_pkg/buildai.spec` | Spec de PyInstaller: qué código y datos (interfaz, skills, addons) se empaquetan |
| `build_pkg/BuildAI.iss` | Script de Inno Setup: carpeta de instalación, accesos directos, desinstalador |
| `build_installer.ps1` | Encadena PyInstaller + Inno Setup en un solo comando |

---

## 🧠 Cómo funciona por dentro

```
┌─────────────┐   chat    ┌──────────────────┐  herramientas  ┌────────────────┐
│  Interfaz    │ ────────► │  Agente BuildAI  │ ─────────────► │ Conectores     │
│ (ventana app)│ ◄──────── │  (bucle de tools)│ ◄───────────── │ Blender 8601   │
└─────────────┘  eventos   └────────┬─────────┘   resultados   │ AutoCAD (COM)  │
                                    │                          │ SketchUp 8602  │
                              proveedor IA                     │ Revit 48884    │
                     (OpenRouter/Claude/GPT/Gemini)            └────────────────┘
```

- **Agente**: el modelo de IA recibe herramientas (`blender_ejecutar_python`,
  `autocad_comando`, `revit_ejecutar_python`…) y las va usando paso a paso
  hasta completar tu petición, verificando resultados.
- **Conectores**: cada programa tiene un puente local (add-on o COM) que solo
  acepta conexiones desde tu propio ordenador (127.0.0.1).
- **Skills**: los archivos de `buildai/skills_data/*.json` son tareas
  predefinidas. Puedes crear las tuyas copiando cualquiera y cambiando el
  texto — aparecerán como botones al recargar la página.
- **Conocimiento de arquitectura**: el agente lleva incorporadas referencias
  de diseño (dimensiones habituales, accesibilidad, estructura, bioclimática…)
  en sus instrucciones internas, para que se comporte como un experto en
  arquitectura sin importar qué proveedor/modelo de IA elijas. Están en
  `buildai/agent.py` (`SISTEMA_BASE`), documentadas y editables si quieres
  ajustarlas a la normativa de tu país.

## ➕ Crear tus propias skills

Crea un archivo `buildai/skills_data/mi-skill.json`:

```json
{
  "id": "mi-skill",
  "nombre": "Nombre del botón",
  "icono": "🏢",
  "descripcion": "Qué hace, en una línea",
  "prompt": "La instrucción completa que se enviará a la IA."
}
```

## ⚠️ Notas de seguridad

- La IA ejecuta código dentro de tus programas para poder trabajar. Trabaja
  siempre sobre **copias de seguridad** de tus proyectos importantes.
- El agente tiene instrucciones de no borrar nada sin confirmarlo, pero los
  modelos de IA pueden equivocarse: revisa los cambios.
- Todos los puentes escuchan solo en `127.0.0.1` (tu propio equipo).

## 🛠️ Problemas frecuentes

| Problema | Solución |
|---|---|
| "Falta la clave de API" | Ajustes ⚙️ → pega tu clave del proveedor elegido |
| El punto de un programa no se pone verde | Pulsa ❓ junto al programa y sigue los pasos; espera ~10 s |
| AutoCAD no conecta | Abre AutoCAD con un dibujo; ejecuta ambos programas con el mismo nivel de permisos |
| El modelo gratuito responde raro o no usa herramientas | En Ajustes, cambia el modelo de OpenRouter por otro que soporte herramientas, o usa Claude/GPT/Gemini |
| Error 429 (límite de peticiones) | BuildAI espera y reintenta solo; si persiste, es el cupo diario del modelo gratuito: elige otro modelo ':free' o usa Ollama local |
| El asistente pausa en tareas muy largas | No es un error: escribe «continúa» y retoma donde quedó |
