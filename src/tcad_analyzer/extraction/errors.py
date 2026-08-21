"""추출 알고리즘 공용 예외."""


class ExtractionError(Exception):
    """Vth/SS/Ion/Ioff/Ron/gm/gds/DIBL 등 추출 계산 실패 시 발생."""
