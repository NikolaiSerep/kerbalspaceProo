import krpc
from time import sleep

def engage(vessel, space_center, connection, ascentProfileConstant=1.25):
    """
    Выводит корабль на низкую опорную орбиту Кербина (LKO) с целевыми параметрами:
    апогей ~75 км, перигей ~70 км.
    Параметр ascentProfileConstant управляет крутизной гравитационного разворота.
    """
    # Включаем систему реактивного управления (RCS) для лучшей стабилизации на взлёте
    vessel.control.rcs = True

    # Полный газ с самого старта
    vessel.control.throttle = 1

    # Создаём поток для отслеживания текущей высоты апогея в реальном времени
    apoapsisStream = connection.add_stream(getattr, vessel.orbit, 'apoapsis_altitude')

    # Включаем автопилот и задаём начальный курс 90° (строго на восток)
    vessel.auto_pilot.engage()
    vessel.auto_pilot.target_heading = 90

    # -------------------------------------------------------------------------
    # ЭТАП 1: Гравитационный разворот и набор высоты до достижения апогея 75 км
    # -------------------------------------------------------------------------
    while apoapsisStream() < 75000:
        # Вычисляем целевой угол тангажа (от вертикали) по мере роста апогея.
        # Формула: targetPitch = 90 - k * (apoapsis ** ascentProfileConstant)
        # где k = 90 / (75000 ** ascentProfileConstant)
        # При старте (apoapsis мал) targetPitch близок к 90° (почти вертикально вверх).
        # По мере приближения апогея к 75 км targetPitch стремится к 0° (горизонтально).
        targetPitch = 90 - ((90 / (75000 ** ascentProfileConstant)) *
                            (apoapsisStream() ** ascentProfileConstant))
        print("Текущий целевой тангаж:", targetPitch, "при апогее", apoapsisStream())

        # Задаём автопилоту новый угол тангажа
        vessel.auto_pilot.target_pitch = targetPitch

        sleep(0.1)  # Небольшая пауза для стабильности управления

    # Как только апогей достиг 75 км, отключаем двигатель
    vessel.control.throttle = 0

    # -------------------------------------------------------------------------
    # ЭТАП 2: Подготовка к циркуляризационному импульсу
    # -------------------------------------------------------------------------
    # Создаём потоки для отслеживания времени до апогея и высоты перигея
    timeToApoapsisStream = connection.add_stream(getattr, vessel.orbit, 'time_to_apoapsis')
    periapsisStream = connection.add_stream(getattr, vessel.orbit, 'periapsis_altitude')

    # Ожидаем, пока до апогея не останется около 22 секунд.
    # Во время ожидания используем ускорение времени для экономии реального времени.
    while timeToApoapsisStream() > 22:
        if timeToApoapsisStream() > 60:
            # Если времени много, включаем высокую скорость варпа (4x)
            space_center.rails_warp_factor = 4
        else:
            # Приближаясь к моменту манёвра, выключаем варп
            space_center.rails_warp_factor = 0
        sleep(0.5)

    # -------------------------------------------------------------------------
    # ЭТАП 3: Циркуляризация
    vessel.control.throttle = 0.5
    lastUT = space_center.ut
    lastTimeToAp = timeToApoapsisStream()
    delta_history = []

    while periapsisStream() < 70500:
        sleep(0.5)
        timeToAp = timeToApoapsisStream()
        UT = space_center.ut
        dt = UT - lastUT
        if dt < 0.001:
            continue
        delta = (timeToAp - lastTimeToAp) / dt
        delta_history.append(delta)
        if len(delta_history) > 5:
            delta_history.pop(0)
        smoothed_delta = sum(delta_history) / len(delta_history)
        
        print(f"Сглаженная оценка: {smoothed_delta:.3f}")
        
        # Коррекция тяги
        if smoothed_delta < -0.3:
            vessel.control.throttle = min(1.0, vessel.control.throttle + 0.03)
        elif smoothed_delta < -0.1:
            vessel.control.throttle = min(1.0, vessel.control.throttle + 0.01)
        if smoothed_delta > 0.2:
            vessel.control.throttle = max(0.0, vessel.control.throttle - 0.03)
        elif smoothed_delta > 0:
            vessel.control.throttle = max(0.0, vessel.control.throttle - 0.01)
        
        lastTimeToAp = timeToAp
        lastUT = UT

    vessel.control.throttle = 0

    # Выводим финальные параметры орбиты для контроля
    print("Апогей: ", apoapsisStream())
    print("Перигей: ", periapsisStream())
    print("Орбита достигнута!")
    print()