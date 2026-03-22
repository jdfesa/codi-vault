# Troubleshooting y Solución de Problemas Frecuentes

Este documento recopila problemas documentados a lo largo del desarrollo de codi-vault, detallando las causas raíz y cómo abordarlas si vuelven a aparecer.

---

## 1. Error: `Unit/Video, cannot be fetched or parsed properly.`

Este es el error genérico que arroja el script cuando falla al procesar la página de un video o curso. Usualmente se manifiesta al intentar iniciar descargas en modo manual o interactivo.

### **Causa Histórica 1: Falso Positivo de Autenticación (El bug de `_pf_session`)**
* **El Problema:** Al ingresar a CodigoFacilito, la plataforma asigna inmediatamente una cookie de sesión anónima llamada `_pf_session`. El script antiguo detectaba cualquier cookie de sesión y finalizaba prematuramente la orden `facilito login`, asumiendo que habías ingresado tus datos cuando en realidad no era así.
* **El Efecto:** Al intentar ejecutar `facilito interactive`, codi-vault enviaba estas "cookies de anonimato", por lo cual el servidor denegaba el acceso al video y redirigía al proceso interno hacia la ruta `/users/sign_in`. Debido a esta redirección, los *crawlers* de Playwright intentaban buscar datos del video en una página de login que no poseía dichos datos, rompiendo el script por tiempo de espera excedido (*Timeout*).
* **Nuestra Solución:** Se parcheó el manejo de identidades en `async_api.py` para ignorar la cookie preliminar. Ahora, el script espera estrictamente la obtención de la cookie `remember_user_token`, la cual únicamente se genera tras una validación exitosa de credenciales reales.

### **Causa Histórica 2: Cambios de DOM y Selectores CSS obsoletos**
* **El Problema:** La plataforma web cambia su diseño y estructura HTML sin previo aviso. Antiguamente, el script extraía el título de la clase buscando exactamente `.title-section header h1`. Cuando actualizaron la plataforma, este encabezado desapareció bajo ese nivel jerárquico.
* **Nuestra Solución:** Se simplificó la regla CSS en `unit.py` a solamente buscar la primera coincidencia de la etiqueta `h1`.
* **Qué hacer si a futuro vuelve a fallar:** Si la plataforma altera sus etiquetas dramáticamente (y tus cookies de login aún no venzan), será requerido actualizar manualmente las reglas CSS que rigen la extracción. Puedes depurar el problema alterando `NAME_SELECTOR` dentro de `src/facilito/collectors/unit.py`.

---

## 2. Dificultades o Errores de Conexión y Protección Anti-Bot (Cloudflare)

### Bloqueos "403 Forbidden" y Captchas Infinitos
* **El Problema:** Codigo Facilito usa Cloudflare para evitar la ejecución de robots. A veces, las descargas en segundo plano (`headless=True`) son catalogadas como maliciosas y la página requerirá que interactúes con el desafío humano clásico (ej. *Just a moment...*).
* **Nuestra Solución:** 
  * En el **modo interactivo**, el prompter incluye una pregunta sobre si tu descarga está fallando por medidas web. Si respondes a la consulta con `n` (apagar modo oculto/headless param), el navegador Playwright se instanciará *de forma visible y humanizada*. Esto permite sortear dinámicamente el chequeo del Captcha o incluso te permite darle el clic manualmente si se tornara extremadamente estricto.
  * Por CLI: Basta con añadir el *flag* `--no-headless` a tu invocación normal de `poetry run facilito download`.

---

## Recomendaciones Generales
Si de repente empiezas a experimentar fallas recurrentes:
1. Corre un `poetry run facilito logout` y vuelve a acceder con `poetry run facilito login`. Nueve de cada diez veces, tu cookie expiró o caducó del lado del servidor.
2. Mantente alerta por correos sobre cierres de sesión forzados; plataformas como Codigo Facilito suelen invalidar sesiones si detectan consumos atípicos asíncronos en múltiples hilos simultáneos. En ese caso, la recomendación es limitar la concurrencia a menos hilos (`--threads 3` en su lugar de 10).
