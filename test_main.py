import unittest
from datetime import datetime, timezone

from main import (
    FUSO_LOCAL,
    STATUS_SEM_AGUA,
    STATUS_TEM_AGUA,
    STATUS_ULTIMO_DIA,
    eh_ultimo_dia_do_periodo,
    status_do_dia,
)


def epoch_ms(ano, mes, dia, hora=5):
    """Formato da API: dia gravado às 05:00 UTC, em milissegundos."""
    return datetime(ano, mes, dia, hora, tzinfo=timezone.utc).timestamp() * 1000


def periodo(inicio, termino):
    return {"inicio": epoch_ms(*inicio), "termino": epoch_ms(*termino), "colapso": 0}


def agora(ano, mes, dia, hora, minuto=0):
    return datetime(ano, mes, dia, hora, minuto, tzinfo=FUSO_LOCAL)


class TestUltimoDiaPeriodo(unittest.TestCase):
    def test_retorna_true_no_ultimo_dia(self):
        p = periodo((2026, 9, 10), (2026, 9, 15))
        self.assertTrue(eh_ultimo_dia_do_periodo(agora(2026, 9, 15, 12), [p]))

    def test_retorna_false_quando_nao_e_ultimo_dia(self):
        p = periodo((2026, 9, 10), (2026, 9, 16))
        self.assertFalse(eh_ultimo_dia_do_periodo(agora(2026, 9, 15, 12), [p]))


class TestStatusDoDia(unittest.TestCase):
    def setUp(self):
        self.periodos = [
            periodo((2026, 10, 6), (2026, 10, 8)),
            periodo((2026, 10, 12), (2026, 10, 14)),
        ]

    def test_primeiro_dia_tem_agua(self):
        self.assertEqual(status_do_dia(agora(2026, 10, 6, 1), self.periodos), STATUS_TEM_AGUA)

    def test_meio_do_periodo_tem_agua(self):
        self.assertEqual(status_do_dia(agora(2026, 10, 7, 15), self.periodos), STATUS_TEM_AGUA)

    def test_ultimo_dia_de_manha(self):
        self.assertEqual(status_do_dia(agora(2026, 10, 8, 0, 30), self.periodos), STATUS_ULTIMO_DIA)

    def test_ultimo_dia_a_noite(self):
        # Antes da correção, depois das 02:00 do último dia a mensagem dizia "não tem água"
        self.assertEqual(status_do_dia(agora(2026, 10, 8, 22), self.periodos), STATUS_ULTIMO_DIA)

    def test_fora_do_periodo_sem_agua(self):
        self.assertEqual(status_do_dia(agora(2026, 10, 10, 9), self.periodos), STATUS_SEM_AGUA)

    def test_dia_seguinte_ao_termino_sem_agua(self):
        self.assertEqual(status_do_dia(agora(2026, 10, 9, 0, 5), self.periodos), STATUS_SEM_AGUA)

    def test_sem_periodos_sem_agua(self):
        self.assertEqual(status_do_dia(agora(2026, 10, 7, 12), []), STATUS_SEM_AGUA)

    def test_ignora_periodos_invalidos(self):
        invalidos = [
            {"inicio": None, "termino": epoch_ms(2026, 10, 7), "colapso": 0},
            {"inicio": epoch_ms(2026, 10, 7), "termino": None, "colapso": 0},
            periodo((2026, 10, 9), (2026, 10, 7)),
        ]
        self.assertEqual(status_do_dia(agora(2026, 10, 7, 12), invalidos), STATUS_SEM_AGUA)

    def test_periodo_que_atravessa_o_mes(self):
        p = [periodo((2026, 10, 30), (2026, 11, 1))]
        self.assertEqual(status_do_dia(agora(2026, 10, 31, 12), p), STATUS_TEM_AGUA)
        self.assertEqual(status_do_dia(agora(2026, 11, 1, 12), p), STATUS_ULTIMO_DIA)


if __name__ == "__main__":
    unittest.main()
