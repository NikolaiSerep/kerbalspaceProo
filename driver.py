import krpc
import time
import _thread as thread
import startLanding
import toLKO
import munTransfer
import stageMonitor
import orbitMun
from telemetry import DataRecorder
# =============================================================================
# 1. ПОДКЛЮЧЕНИЕ К ИГРЕ И ЗАПУСК МОНИТОРИНГА СТУПЕНЕЙ
# =============================================================================
connection = krpc.connect("Connection")
space_center = connection.space_center
vessel = space_center.active_vessel

recorder = DataRecorder(vessel, space_center, interval=0.5)
recorder.start()

args = [vessel]
thread.start_new_thread(stageMonitor.monitor, tuple(args))

# =============================================================================
# 2. ВЗЛЁТ И ВЫХОД НА ОРБИТУ КЕРБИНА
# =============================================================================
print("Этап 1: Взлёт и выход на орбиту Кербина")
toLKO.engage(vessel, space_center, connection, 0.5)

# =============================================================================
# 3. ПЕРЕЛЁТ К МУНЕ (ГОМАНОВСКАЯ ТРАЕКТОРИЯ)
# =============================================================================
print("Этап 2: Перелёт к Муне")
munTransfer.engage(vessel, space_center, connection)

# Вычисляем время до входа в сферу влияния Муны и до её перицентра
time_to_warp = vessel.orbit.next_orbit.time_to_periapsis + vessel.orbit.time_to_soi_change
# Варпим до момента за 5 минут до перицентра (чтобы успеть подготовиться)
space_center.warp_to(space_center.ut + time_to_warp - 300)

# Get ready for landing
orbitMun.engage(vessel, space_center, connection)

# Engage Landing (vertical)
vessel.auto_pilot.engage()
vessel.auto_pilot.reference_frame = vessel.surface_velocity_reference_frame
vessel.auto_pilot.target_direction = (0.0, -1.0, 0.0)  # Point retro-grade surface
print("Stabilizing...")
time.sleep(10)
vessel.auto_pilot.disengage()
vessel.control.sas = True

# Останавливаем сбор данных и строим графики телеметрии
recorder.stop()
recorder.plot(show=True, save_path="my_mission.png")
print("Графики готовы. Программа завершена.")