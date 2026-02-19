import krpc
import time
import math

def engage(vessel, space_center, connection):
    """
    Выполняет торможение в перицентре Муны для выхода на круговую орбиту.
    Целевая высота орбиты: 30 км над поверхностью Муны (можно изменить).
    """
    print("Начинаем манёвр торможения для выхода на орбиту Муны...")

    # Параметры Муны
    mun = space_center.bodies["Mun"]
    mu_mun = mun.gravitational_parameter
    r_mun = mun.equatorial_radius

    # Целевая высота круговой орбиты (например, 30 км)
    target_altitude = 30000  # метры
    target_radius = r_mun + target_altitude

    # Ожидаем точного момента перицентра
    print("Ожидание перицентра...")
    while vessel.orbit.time_to_periapsis > 2:
        if vessel.orbit.time_to_periapsis > 60:
            space_center.rails_warp_factor = 5
        else:
            space_center.rails_warp_factor = 0
        time.sleep(0.5)
    space_center.rails_warp_factor = 0
    print("Вошли в перицентр.")

    # Текущая скорость в перицентре (относительно Муны)
    v_current = vessel.flight(mun.reference_frame).speed
    # Радиус перицентра (расстояние до центра Муны)
    r_peri = vessel.orbit.periapsis

    # Скорость для круговой орбиты на этой высоте (vis-viva для круговой: v = sqrt(mu/r))
    v_target = math.sqrt(mu_mun / r_peri)

    # Потребная дельта V (торможение)
    deltaV = v_current - v_target
    if deltaV < 0:
        print("Предупреждение: текущая скорость ниже целевой. Возможно, нужно разгоняться.")
        deltaV = abs(deltaV)
        direction = (0.0, 1.0, 0.0)  # prograde
    else:
        direction = (0.0, -1.0, 0.0)  # retrograde

    print(f"Текущая скорость: {v_current:.1f} м/с, целевая: {v_target:.1f} м/с")
    print(f"Потребная дельта V: {deltaV:.1f} м/с")

    # Ориентация
    vessel.auto_pilot.engage()
    vessel.auto_pilot.reference_frame = vessel.orbital_reference_frame
    vessel.auto_pilot.target_direction = direction
    vessel.auto_pilot.wait()
    print("Ориентация завершена.")

    # Выполнение импульса
    vessel.control.throttle = 1.0
    initial_speed = vessel.flight(mun.reference_frame).speed
    achieved_dv = 0.0

    while achieved_dv < deltaV:
        time.sleep(0.1)
        current_speed = vessel.flight(mun.reference_frame).speed
        achieved_dv = abs(initial_speed - current_speed)
        print(f"Набрано дельты: {achieved_dv:.1f} из {deltaV:.1f}")

    vessel.control.throttle = 0.0
    vessel.auto_pilot.disengage()
    print("Манёвр завершён. Корабль вышел на орбиту Муны.")
    print(f"Текущие параметры: апогей {vessel.orbit.apoapsis_altitude/1000:.1f} км, перигей {vessel.orbit.periapsis_altitude/1000:.1f} км")