import asyncio
from nicegui import app, ui

from communication_library.communication_manager import CommunicationManager, TransportType
from communication_library.tcp_transport import TcpSettings
from communication_library.frame import Frame
from communication_library import ids


# Zawory:
ZAWOR_PALIWA_INTAKE = 0        # fuel_intake
ZAWOR_UTLENIACZA_INTAKE = 1    # oxidizer_intake
ZAWOR_PALIWA_GLOWNY = 2        # fuel_main
ZAWOR_UTLENIACZA_GLOWNY = 3    # oxidizer_main

# Przełączniki:
GRZALKA_UTLENIACZA = 0         # oxidizer_heater
ZAPLONNIK = 1                  # igniter
SPADOCHRON = 2                 # parachute

# Czujniki:
CZUJNIK_PALIWA = 0             # fuel_level
CZUJNIK_UTLENIACZA = 1         # oxidizer_level
CZUJNIK_WYSOKOSCI = 2          # altitude
CZUJNIK_CISNIENIA = 3          # oxidizer_pressure

dane_telemetrii = {
    'wysokosc': 0.0,
    'poziom_utleniacza': 0.0,
    'poziom_paliwa': 0.0,
    'cisnienie_utleniacza': 0.0
}

manager = CommunicationManager()

def otworz_zawor(id_zaworu: int):
    """Otwiera zawór (pozycja 0)"""
    ramka = Frame(
        destination=ids.BoardID.ROCKET,
        priority=ids.PriorityID.LOW,
        action=ids.ActionID.SERVICE,
        source=ids.BoardID.SOFTWARE,
        device=ids.DeviceID.SERVO,
        device_id=id_zaworu,
        data_type=ids.DataTypeID.INT16,
        operation=ids.OperationID.SERVO.value.POSITION,
        payload=(0,)
    )
    manager.push(ramka)
    manager.send()


def zamknij_zawor(id_zaworu: int):
    """Zamyka zawór (pozycja 100)"""
    ramka = Frame(
        destination=ids.BoardID.ROCKET,
        priority=ids.PriorityID.LOW,
        action=ids.ActionID.SERVICE,
        source=ids.BoardID.SOFTWARE,
        device=ids.DeviceID.SERVO,
        device_id=id_zaworu,
        data_type=ids.DataTypeID.INT16,
        operation=ids.OperationID.SERVO.value.POSITION,
        payload=(100,)
    )
    manager.push(ramka)
    manager.send()


def wlacz_urzadzenie(id_urzadzenia: int):
    ramka = Frame(
        destination=ids.BoardID.ROCKET,
        priority=ids.PriorityID.LOW,
        action=ids.ActionID.SERVICE,
        source=ids.BoardID.SOFTWARE,
        device=ids.DeviceID.RELAY,
        device_id=id_urzadzenia,
        data_type=ids.DataTypeID.FLOAT,
        operation=ids.OperationID.RELAY.value.OPEN,
        payload=()
    )
    manager.push(ramka)
    manager.send()


def wylacz_urzadzenie(id_urzadzenia: int):
    ramka = Frame(
        destination=ids.BoardID.ROCKET,
        priority=ids.PriorityID.LOW,
        action=ids.ActionID.SERVICE,
        source=ids.BoardID.SOFTWARE,
        device=ids.DeviceID.RELAY,
        device_id=id_urzadzenia,
        data_type=ids.DataTypeID.FLOAT,
        operation=ids.OperationID.RELAY.value.CLOSE,
        payload=()
    )
    manager.push(ramka)
    manager.send()

async def sekwencja_startowa():
    ui.notify("Rozpoczynamy procedurę startową!")

    # TANKOWANIE UTLENIACZA
    napis_statusu.set_text("STATUS: Tankowanie utleniacza...")
    otworz_zawor(ZAWOR_UTLENIACZA_INTAKE)

    while dane_telemetrii['poziom_utleniacza'] < 100:
        await asyncio.sleep(0.1)

    zamknij_zawor(ZAWOR_UTLENIACZA_INTAKE)

    # TANKOWANIE PALIWA
    napis_statusu.set_text("STATUS: Tankowanie paliwa...")
    otworz_zawor(ZAWOR_PALIWA_INTAKE)

    while dane_telemetrii['poziom_paliwa'] < 100:
        await asyncio.sleep(0.1)

    zamknij_zawor(ZAWOR_PALIWA_INTAKE)

    # PODGRZEWANIE UTLENIACZA
    napis_statusu.set_text("STATUS: Podgrzewanie utleniacza...")
    wlacz_urzadzenie(GRZALKA_UTLENIACZA)

    while dane_telemetrii['cisnienie_utleniacza'] < 58:
        await asyncio.sleep(0.1)

    wylacz_urzadzenie(GRZALKA_UTLENIACZA)

    #ZAPŁON SILNIKA
    napis_statusu.set_text("STATUS: ZAPŁON!")
    otworz_zawor(ZAWOR_PALIWA_GLOWNY)
    otworz_zawor(ZAWOR_UTLENIACZA_GLOWNY)

    await asyncio.sleep(0.1)
    wlacz_urzadzenie(ZAPLONNIK)

    # LOT I SPADOCHRON
    napis_statusu.set_text("STATUS: Rakieta leci! Śledzenie wysokości...")

    maksymalna_wysokosc = 0.0

    while True:
        await asyncio.sleep(0.1)
        aktualna_wysokosc = dane_telemetrii['wysokosc']

        if aktualna_wysokosc > maksymalna_wysokosc:
            maksymalna_wysokosc = aktualna_wysokosc
        elif aktualna_wysokosc < maksymalna_wysokosc - 3.0:
            napis_statusu.set_text("STATUS: Wykryto opadanie! Wypuszczam spadochron!")
            wlacz_urzadzenie(SPADOCHRON)
            break

    napis_statusu.set_text("STATUS: Spadochron otwarty. Lądowanie...")

async def odbieraj_telemetrie():
    manager.change_transport_type(TransportType.TCP)
    try:
        manager.connect(TcpSettings("127.0.0.1", 3000))
    except Exception:
        pass

    while True:
        try:
            ramka = manager.receive()
            if ramka and ramka.payload is not None:
                if isinstance(ramka.payload, (tuple, list)) and len(ramka.payload) > 0:
                    wartosc = float(ramka.payload[0])
                else:
                    wartosc = float(ramka.payload)

                if ramka.device_id == CZUJNIK_PALIWA:
                    dane_telemetrii['poziom_paliwa'] = wartosc
                elif ramka.device_id == CZUJNIK_UTLENIACZA:
                    dane_telemetrii['poziom_utleniacza'] = wartosc
                elif ramka.device_id == CZUJNIK_WYSOKOSCI:
                    dane_telemetrii['wysokosc'] = wartosc
                elif ramka.device_id == CZUJNIK_CISNIENIA:
                    dane_telemetrii['cisnienie_utleniacza'] = wartosc
        except Exception:
            pass

        await asyncio.sleep(0.01)


ui.label('🚀 Panel Sterowania Rakietą').classes('text-3xl font-bold mb-4')
napis_statusu = ui.label('STATUS: Oczekiwanie na start...').classes('text-xl text-blue-500 font-bold mb-4')

ui.button('🚀 ROZPOCZNIJ SEKWENCJĘ STARTOWĄ', on_click=sekwencja_startowa).classes('mb-8')

app.on_startup(odbieraj_telemetrie)

ui.run(port=8080)
