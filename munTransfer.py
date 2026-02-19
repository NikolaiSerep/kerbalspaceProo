import krpc
from time import sleep
import math

def engage(vessel, space_center, connection):
    """
    Выполняет манёвр перехода к Луне (Муне) с орбиты Кербина.
    """
    # Подготовка корабля
    vessel.control.rcs = True
    for fairing in vessel.parts.fairings:
        fairing.jettison()
    vessel.control.antennas = True

    # Получаем данные о Луне один раз
    mun = space_center.bodies["Mun"]
    mun_orbit = mun.orbit
    mun_semi_major = mun_orbit.semi_major_axis
    mun_radius = mun_orbit.radius

    # ---- Точный расчёт оптимального фазового угла ----
    r1 = vessel.orbit.radius
    r2 = mun_semi_major  # или mun_orbit.radius (оба практически равны для круговой орбиты)
    mu = vessel.orbit.body.gravitational_parameter

    # Период переходного эллипса (половина периода)
    a_transfer = (r1 + r2) / 2
    T_transfer = math.pi * math.sqrt(a_transfer**3 / mu)

    # Угловая скорость Муны
    omega_mun = math.sqrt(mu / r2**3)

    # Угол, на который сместится Муна за время перелёта
    theta = omega_mun * T_transfer

    # Оптимальный фазовый угол (в радианах) – отставание корабля от Муны
    optimal_phase_rad = math.pi - theta
    optimal_phase_angle = math.degrees(optimal_phase_rad)

    print(f"Оптимальный фазовый угол: {optimal_phase_angle:.2f}°")

    # Ожидание нужного фазового угла
    vessel.auto_pilot.engage()
    vessel.auto_pilot.reference_frame = vessel.orbital_reference_frame
    vessel.auto_pilot.target_direction = (0.0, 1.0, 0.0)  # prograde

    phase_angle = 1080.0  # начальное значение
    prev_phase = 0.0
    angle_decreasing = False

    # Для расчёта фазового угла используем систему отсчёта Луны, чтобы не пересоздавать каждый раз
    mun_ref_frame = mun.reference_frame

    while abs(phase_angle - optimal_phase_angle) > 1.0 or not angle_decreasing:
        # Получаем текущие радиусы орбит (могут меняться, если орбита не круговая, но для Кербина почти круговая)
        vessel_radius = vessel.orbit.radius

        # Позиции в системе отсчёта Луны
        mun_pos = mun_orbit.position_at(space_center.ut, mun_ref_frame)
        vessel_pos = vessel.orbit.position_at(space_center.ut, mun_ref_frame)

        # Расстояние между кораблём и Луной
        dx = mun_pos[0] - vessel_pos[0]
        dy = mun_pos[1] - vessel_pos[1]
        dz = mun_pos[2] - vessel_pos[2]
        distance = math.sqrt(dx*dx + dy*dy + dz*dz)

        # Фазовый угол через теорему косинусов (в радианах)
        # Чтобы избежать ошибок округления, ограничиваем аргумент арккосинуса диапазоном [-1, 1]
        cos_arg = (mun_radius**2 + vessel_radius**2 - distance**2) / (2 * mun_radius * vessel_radius)
        cos_arg = max(-1.0, min(1.0, cos_arg))  # защита от выхода за пределы
        phase_angle_rad = math.acos(cos_arg)
        phase_angle = math.degrees(phase_angle_rad)

        # Определяем тенденцию изменения угла
        if prev_phase - phase_angle > 0:
            angle_decreasing = True
            # Управление ускорением времени
            if abs(phase_angle - optimal_phase_angle) > 20:
                space_center.rails_warp_factor = 2
            else:
                space_center.rails_warp_factor = 0
        else:
            angle_decreasing = False
            space_center.rails_warp_factor = 4

        prev_phase = phase_angle
        print("Фазовый угол: {:.2f}".format(phase_angle))
        sleep(0.2)  # пауза между измерениями

    # Выключаем варп, если он ещё включён
    space_center.rails_warp_factor = 0

    # Расчёт потребной дельты V
    GM = vessel.orbit.body.gravitational_parameter
    r = vessel.orbit.radius
    a_initial = vessel.orbit.semi_major_axis

    # Текущая скорость
    v_initial = math.sqrt(GM * (2.0/r - 1.0/a_initial))

    # Большая полуось переходного эллипса (от текущей орбиты до орбиты Луны)
    a_transfer = (r + mun_radius) / 2.0
    v_transfer = math.sqrt(GM * (2.0/r - 1.0/a_transfer))

    deltaV = v_transfer - v_initial
    print("Maneuver Now With DeltaV: {:.2f} m/s".format(deltaV))

    # Выполнение манёвра
    vessel.control.throttle = 1.0
    actual_dv = 0.0

    while deltaV > actual_dv:
        sleep(0.15)
        # Текущая скорость 
        r = vessel.orbit.radius
        a_current = vessel.orbit.semi_major_axis
        v_current = math.sqrt(GM * (2.0/r - 1.0/a_current))
        actual_dv = v_current - v_initial
        print("DeltaV пока: {:.2f} необходимо {:.2f}".format(actual_dv, deltaV))

    vessel.control.throttle = 0.0
    vessel.auto_pilot.disengage()
    print("встреча с лунойстан!")
