# lab-stand-controller

MVP backend для лабораторного стенда с двумя Arduino: safety/master и student/controller. Работает на ПК/РPi, позже переносится на Raspberry Pi без существенных изменений.

Пример telemetry (v0.1):

```json
{"type":"telemetry","ver":"0.1","ts":1710000000000,"t1":23.4,"t2":25.1,"t3":24.0,"p1":1.02,"p2":0.98,"flow":3.4,"heater":0,"pump":120,"fan":[80,80,80],"drain_valve":0,"fault":0}
```

## Быстрый старт (Docker, SIM_MODE)

```bash
docker compose up --build
```

Откройте:
- http://localhost:8000/ui/teacher
- http://localhost:8000/ui/student

По умолчанию контейнер запускается в `SIM_MODE=true`, телеметрия генерируется сервером.

## Локальный запуск (venv, реальное железо)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SAFETY_PORT=/dev/ttyACM0
export STUDENT_PORT=/dev/ttyACM1
export SIM_MODE=false
export UPLOAD_ENABLED=true

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Переменные окружения

- `SAFETY_PORT` — порт Arduino #1 (safety/master)
- `STUDENT_PORT` — порт Arduino #2 (student/controller)
- `BAUDRATE` — скорость (по умолчанию `115200`)
- `SIM_MODE` — `true/false`, генерация телеметрии без serial
- `ARDUINO_CLI_PATH` — путь к `arduino-cli` (по умолчанию `arduino-cli`)
- `UPLOAD_ENABLED` — `true/false`, разрешить прошивку Arduino #2
- `DATA_DIR` — директория для базы и uploads (по умолчанию `/data`)
- `BASELINE_FQBN` — FQBN для baseline-прошивки (по умолчанию `arduino:avr:uno`)
- `BASELINE_SKETCH_MAIN` — имя .ino для baseline zip (опционально)

## Примеры curl

```bash
# heater manual
curl -X POST http://localhost:8000/api/teacher/heater/manual \
  -H 'Content-Type: application/json' \
  -d '{"power":60}'

# heater random
curl -X POST http://localhost:8000/api/teacher/heater/random \
  -H 'Content-Type: application/json' \
  -d '{"min":20,"max":80,"on_min_s":2,"on_max_s":10,"off_min_s":2,"off_max_s":10}'

# stop heater
curl -X POST http://localhost:8000/api/teacher/heater/stop

# student actuators
curl -X POST http://localhost:8000/api/student/actuators \
  -H 'Content-Type: application/json' \
  -d '{"pump":120,"fan":[80,70,60]}'

# drain valve (safety)
curl -X POST http://localhost:8000/api/teacher/drain_valve \
  -H 'Content-Type: application/json' \
  -d '{"open":true}'

# student mode
curl -X POST http://localhost:8000/api/teacher/student_mode \
  -H 'Content-Type: application/json' \
  -d '{"mode":"student"}'
```

## Загрузка прошивки (Arduino #2)

```bash
curl -X POST http://localhost:8000/api/student/firmware/upload \
  -F "file=@/path/to/sketch.ino" \
  -F "board_fqbn=arduino:avr:uno"
```

Для ZIP-архива:

```bash
curl -X POST http://localhost:8000/api/student/firmware/upload \
  -F "file=@/path/to/project.zip" \
  -F "board_fqbn=arduino:avr:uno" \
  -F "sketch_main=main.ino"
```

Прошивка доступна только для Arduino #2 и всегда использует `STUDENT_PORT`.

## Student mode и baseline

Преподаватель переключает режим Arduino #2:
- `baseline`: web-actuators разрешены, upload студента отключен.
- `student`: upload студента разрешен, web-actuators отключены.

При `baseline` сервер пытается прошить baseline-скетч, если он добавлен в `app/baseline_firmware/`. Если базовая прошивка не предоставлена, режим все равно включится и вернет предупреждение.

## Docker + serial

Linux (пример проброса портов):

```yaml
services:
  lab-stand-controller:
    devices:
      - "/dev/ttyACM0:/dev/ttyACM0"
      - "/dev/ttyACM1:/dev/ttyACM1"
```

Windows/Mac: доступ к serial из Docker обычно затруднен. Рекомендуется запускать нативно через venv для реальной прошивки и управления железом. В Docker гарантированно работает `SIM_MODE`.

## Известные ограничения

- В `SIM_MODE` прошивка может быть отключена через `UPLOAD_ENABLED=false`.
- Протокол serial v0.1 поддерживается на уровне JSON Lines, ошибки парсинга игнорируются.
- `drain_valve` и `heater` всегда идут только на SAFETY_PORT, прошивка всегда только на STUDENT_PORT.
