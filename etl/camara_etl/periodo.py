"""Janela de tempo coberta pelo painel."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

BRT = timezone(timedelta(hours=-3))


@dataclass(frozen=True)
class Periodo:
    inicio: date
    fim: date

    @property
    def ini(self) -> str:
        """Primeiro dia incluído, como texto ISO (compara com prefixos de data e data-hora)."""
        return self.inicio.isoformat()

    @property
    def fim_excl(self) -> str:
        """Dia seguinte ao último incluído: datas válidas são < fim_excl."""
        return (self.fim + timedelta(days=1)).isoformat()

    def contem(self, quando: str | None) -> bool:
        return bool(quando) and self.ini <= quando < self.fim_excl

    @property
    def anos(self) -> list[int]:
        return list(range(self.inicio.year, self.fim.year + 1))

    @property
    def meses(self) -> list[str]:
        out, y, m = [], self.inicio.year, self.inicio.month
        while (y, m) <= (self.fim.year, self.fim.month):
            out.append(f"{y}-{m:02d}")
            m += 1
            if m > 12:
                y, m = y + 1, 1
        return out


def periodo_padrao(anos: int = 4, fim: date | None = None) -> Periodo:
    fim = fim or datetime.now(BRT).date()
    try:
        inicio = fim.replace(year=fim.year - anos)
    except ValueError:  # 29 de fevereiro
        inicio = fim.replace(year=fim.year - anos, day=28)
    return Periodo(inicio=inicio, fim=fim)
