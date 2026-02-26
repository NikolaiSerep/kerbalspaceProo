import threading
import time
import matplotlib.pyplot as plt
import numpy as np
import math

class DataRecorder:
    """
    Сбор телеметрии на всём протяжении миссии (от старта до посадки на Муну).
    """
    def __init__(self, vessel, space_center, interval=0.5):
        self.vessel = vessel
        self.space_center = space_center
        self.interval = interval
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        self.start_ut = None

        # Списки для данных
        self.time = []
        self.altitude = []           # высота над поверхностью (м)
        self.vertical_speed = []      # вертикальная скорость (м/с)
        self.speed = []               # полная скорость (м/с)
        self.mass = []                # масса корабля (кг)
        self.throttle = []            # положение дросселя (0..1)
        self.apoapsis = []            # высота апогея (м)
        self.periapsis = []           # высота перигея (м)
        self.dynamic_pressure = []    # динамическое давление Q (Па) – для атмосферы
        self.mach = []                # число Маха
        self.acceleration = []        # полное ускорение (м/с²)

    def _record(self):
        """Сбор одного набора данных"""
        if self.start_ut is None:
            self.start_ut = self.space_center.ut

        flight = self.vessel.flight()
        orbit = self.vessel.orbit

        with self.lock:
            self.time.append(self.space_center.ut - self.start_ut)
            self.altitude.append(flight.surface_altitude)
            self.vertical_speed.append(flight.vertical_speed)
            self.speed.append(flight.speed)
            self.mass.append(self.vessel.mass)
            self.throttle.append(self.vessel.control.throttle)
            self.apoapsis.append(orbit.apoapsis_altitude)
            self.periapsis.append(orbit.periapsis_altitude)
            self.dynamic_pressure.append(flight.dynamic_pressure)
            self.mach.append(flight.mach)
            self.acceleration.append(flight.g_force * 9.81)  # в м/с²

    def _loop(self):
        """Основной цикл сбора данных"""
        while self.running:
            self._record()
            time.sleep(self.interval)

    def start(self):
        """Запустить поток сбора данных"""
        if self.thread is not None and self.thread.is_alive():
            print("⚠️ Сбор данных уже запущен.")
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        print("📈 Сбор телеметрии запущен (интервал {:.1f} с)".format(self.interval))

    def stop(self):
        """Остановить поток сбора данных"""
        self.running = False
        if self.thread is not None:
            self.thread.join()
        print("⏹️ Сбор телеметрии остановлен.")

    def get_data(self):
        """Возвращает копию всех данных (потокобезопасно)"""
        with self.lock:
            return {key: val.copy() for key, val in self.__dict__.items() if key in [
                'time', 'altitude', 'vertical_speed', 'speed', 'mass', 'throttle',
                'apoapsis', 'periapsis', 'dynamic_pressure', 'mach', 'acceleration'
            ]}

    def plot(self, show=True, save_path='mission_telemetry.png'):
        """
        Построить 9 графиков, охватывающих всю миссию.
        """
        data = self.get_data()
        if not data['time']:
            print("⚠️ Нет данных для построения графиков.")
            return

        # Красивый стиль
        plt.style.use('seaborn-v0_8-darkgrid')
        fig, axes = plt.subplots(3, 3, figsize=(16, 10))
        fig.suptitle('📊 Телеметрия миссии: Кербин → Муна (посадка)', fontsize=16, fontweight='bold')

        # 1. Высота над поверхностью
        axes[0,0].plot(data['time'], data['altitude'], color='blue', linewidth=1.2)
        axes[0,0].set_xlabel('Время (с)')
        axes[0,0].set_ylabel('Высота (м)')
        axes[0,0].set_title('Высота над поверхностью')
        axes[0,0].grid(True, linestyle='--', alpha=0.7)
        axes[0,0].fill_between(data['time'], 0, data['altitude'], alpha=0.2, color='blue')

        # 2. Вертикальная скорость
        axes[0,1].plot(data['time'], data['vertical_speed'], color='red', linewidth=1.2)
        axes[0,1].set_xlabel('Время (с)')
        axes[0,1].set_ylabel('Вертикальная скорость (м/с)')
        axes[0,1].set_title('Вертикальная скорость')
        axes[0,1].grid(True, linestyle='--', alpha=0.7)
        axes[0,1].axhline(y=0, color='black', linestyle='-', linewidth=0.5)

        # 3. Полная скорость
        axes[0,2].plot(data['time'], data['speed'], color='green', linewidth=1.2)
        axes[0,2].set_xlabel('Время (с)')
        axes[0,2].set_ylabel('Скорость (м/с)')
        axes[0,2].set_title('Полная скорость')
        axes[0,2].grid(True, linestyle='--', alpha=0.7)

                # 4. Масса корабля
        axes[1,0].plot(data['time'], data['mass'], color='purple', linewidth=1.2)
        axes[1,0].set_xlabel('Время (с)')
        axes[1,0].set_ylabel('Масса (кг)')
        axes[1,0].set_title('Масса корабля')
        axes[1,0].grid(True, linestyle='--', alpha=0.7)
        axes[1,0].fill_between(data['time'], np.min(data['mass']), data['mass'], alpha=0.2, color='purple')

        # 5. Тяга (дроссель)
        axes[1,1].plot(data['time'], data['throttle'], color='orange', linewidth=1.2)
        axes[1,1].set_xlabel('Время (с)')
        axes[1,1].set_ylabel('Дроссель (0-1)')
        axes[1,1].set_title('Управление тягой')
        axes[1,1].set_ylim(-0.1, 1.1)
        axes[1,1].grid(True, linestyle='--', alpha=0.7)

        # 6. Апогей и перигей (орбитальные параметры, в км)
        axes[1,2].plot(data['time'], np.array(data['apoapsis'])/1000, label='Апогей', color='darkblue', linewidth=1.2)
        axes[1,2].plot(data['time'], np.array(data['periapsis'])/1000, label='Перигей', color='darkgreen', linewidth=1.2)
        axes[1,2].set_xlabel('Время (с)')
        axes[1,2].set_ylabel('Высота (км)')
        axes[1,2].set_title('Орбитальные параметры')
        axes[1,2].grid(True, linestyle='--', alpha=0.7)
        axes[1,2].legend()

        # 7. Динамическое давление Q (атмосфера)
        axes[2,0].plot(data['time'], data['dynamic_pressure'], color='brown', linewidth=1.2)
        axes[2,0].set_xlabel('Время (с)')
        axes[2,0].set_ylabel('Q (Па)')
        axes[2,0].set_title('Динамическое давление')
        axes[2,0].grid(True, linestyle='--', alpha=0.7)

        # 8. Число Маха
        axes[2,1].plot(data['time'], data['mach'], color='magenta', linewidth=1.2)
        axes[2,1].set_xlabel('Время (с)')
        axes[2,1].set_ylabel('Число Маха')
        axes[2,1].set_title('Число Маха')
        axes[2,1].grid(True, linestyle='--', alpha=0.7)

        # 9. Ускорение (перегрузка)
        axes[2,2].plot(data['time'], data['acceleration'], color='gray', linewidth=1.2)
        axes[2,2].set_xlabel('Время (с)')
        axes[2,2].set_ylabel('Ускорение (м/с²)')
        axes[2,2].set_title('Полное ускорение')
        axes[2,2].grid(True, linestyle='--', alpha=0.7)

        plt.tight_layout(rect=[0, 0, 1, 0.96])

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"💾 Графики сохранены в '{save_path}'")

        if show:
            plt.show()
        else:
            plt.close()