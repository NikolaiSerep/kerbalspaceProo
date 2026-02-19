# Основной файл миссии: облёт Муны и возврат на Кербин с посадкой
import krpc
import time
import _thread as thread
import toLKO
import munTransfer
import stageMonitor
from telemetry import DataRecorder
import math  # может пригодиться для других расчётов

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

# =============================================================================
# 4. ОЖИДАНИЕ ВЫХОДА ИЗ СФЕРЫ МУНЫ (С УСКОРЕНИЕМ ВРЕМЕНИ)
# =============================================================================

print("Этап 3: Ожидание выхода из сферы Муны...")
while vessel.orbit.body.name == "Mun":
    # Ускоряем время, если мы далеко от перицентра (до или после)
    if abs(vessel.orbit.time_to_periapsis) > 60:
        space_center.rails_warp_factor = 7  # можно 7 для максимального ускорения
    else:
        space_center.rails_warp_factor = 0
    time.sleep(1)
space_center.rails_warp_factor = 0
print("Корабль покинул сферу Муны и вышел на орбиту Кербина.")
# =============================================================================
# 5. КОРРЕКЦИЯ ТРАЕКТОРИИ ДЛЯ ТОЧНОГО ВХОДА В АТМОСФЕРУ
# =============================================================================
print("Этап 4: Коррекция траектории для возврата на Кербин")

print("Мы на орбите Кербина. Текущие параметры:")
print(f"Апогей: {vessel.orbit.apoapsis_altitude/1000:.1f} км, Перигей: {vessel.orbit.periapsis_altitude/1000:.1f} км")

# Если перицентр уже ниже 70 км, корабль сам войдёт в атмосферу — коррекция не нужна
if vessel.orbit.periapsis_altitude < 70000:
    print("Перигей в атмосфере. Коррекция не требуется.")
else:
    print("Перигей слишком высок. Ожидаем апоцентра для корректирующего торможения...")

    # Ждём подлёта к апоцентру (до него должно остаться ~30 секунд)
    while vessel.orbit.time_to_apoapsis > 30:
        if vessel.orbit.time_to_apoapsis > 120:
            space_center.rails_warp_factor = 4
        else:
            space_center.rails_warp_factor = 0
        time.sleep(0.5)
    space_center.rails_warp_factor = 0
    print("Подлетаем к апоцентру. Готовимся к торможению.")

    # Целевая высота перицентра (30 км) – гарантированный вход в плотные слои атмосферы
    target_pe_alt = 30000
    target_pe_radius = vessel.orbit.body.equatorial_radius + target_pe_alt

    GM = vessel.orbit.body.gravitational_parameter
    r_ap = vessel.orbit.apoapsis
    a_current = vessel.orbit.semi_major_axis

    # Текущая скорость в апоцентре (по уравнению vis-viva)
    v_ap_current = (GM * (2/r_ap - 1/a_current))**0.5

    # Большая полуось целевой орбиты с тем же апоцентром, но нужным перицентром
    a_target = (r_ap + target_pe_radius) / 2
    v_ap_target = (GM * (2/r_ap - 1/a_target))**0.5

    # Потребное изменение скорости (торможение) – разность скоростей в апоцентре
    deltaV = v_ap_current - v_ap_target
    print(f"Потребная дельта V: {deltaV:.1f} м/с")

    # Ориентация на ретроград (торможение) в орбитальной системе отсчёта
    vessel.auto_pilot.engage()
    vessel.auto_pilot.reference_frame = vessel.orbital_reference_frame
    vessel.auto_pilot.target_direction = (0.0, -1.0, 0.0)  # retrograde
    vessel.auto_pilot.wait()
    print("Ориентация завершена.")

    # Выполняем импульс с контролем набранной дельты (используем половину тяги для точности)
    vessel.control.throttle = 0.5
    initial_speed = vessel.flight(vessel.orbit.body.reference_frame).speed
    achieved_dv = 0.0

    while achieved_dv < deltaV:
        time.sleep(0.1)
        current_speed = vessel.flight(vessel.orbit.body.reference_frame).speed
        achieved_dv = initial_speed - current_speed
        print(f"Набрано дельты: {achieved_dv:.1f} из {deltaV:.1f}")

    vessel.control.throttle = 0.0
    vessel.auto_pilot.disengage()
    print("Коррекция завершена.")
    print(f"Новый перигей: {vessel.orbit.periapsis_altitude/1000:.1f} км")

# =============================================================================
# 6. ВХОД В АТМОСФЕРУ И ПОСАДКА
# =============================================================================
print("Этап 5: Вход в атмосферу и посадка")

# Ожидаем, пока перицентр опустится ниже 70 км (автоматический вход)
print("Ожидание входа в атмосферу...")
while vessel.orbit.periapsis_altitude > 70000:
    if vessel.orbit.time_to_periapsis > 60:
        space_center.rails_warp_factor = 4
    else:
        space_center.rails_warp_factor = 0
    time.sleep(1)
space_center.rails_warp_factor = 0

print("Вход в атмосферу. Начинаем спуск.")

# Ориентируем корабль теплозащитным экраном вперёд (ретроград поверхности)
vessel.auto_pilot.engage()
vessel.auto_pilot.reference_frame = vessel.surface_velocity_reference_frame
vessel.auto_pilot.target_direction = (0.0, -1.0, 0.0)  # Ретроград
vessel.auto_pilot.wait()

# Убираем солнечные панели и антенны, чтобы они не сгорели от аэродинамического нагрева
vessel.control.solar_panels = False
vessel.control.antennas = False

# Ждём снижения до высоты, безопасной для раскрытия парашютов
print("Ожидание безопасной высоты для парашютов...")
while True:
    flight_info = vessel.flight()
    altitude = flight_info.mean_altitude
    speed = flight_info.speed
    if altitude < 5000 and speed < 250:
        print(f"Высота: {altitude:.0f} м, скорость: {speed:.0f} м/с — раскрываем парашюты")
        vessel.control.parachutes = True
        break
    time.sleep(0.5)

# Ожидание касания поверхности
print("Парашюты раскрыты, ждём касания...")
while vessel.flight().surface_altitude > 5:
    time.sleep(1)

# Завершение миссии
vessel.control.throttle = 0.0
vessel.auto_pilot.disengage()
vessel.control.sas = True

print("=" * 50)
print("МИССИЯ УСПЕШНО ЗАВЕРШЕНА! КОРАБЛЬ ВЕРНУЛСЯ НА КЕРБИН.")
print("=" * 50)

# Останавливаем сбор данных и строим графики телеметрии
recorder.stop()
recorder.plot(show=True, save_path="my_mission.png")
print("Графики готовы. Программа завершена.")