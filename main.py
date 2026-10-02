import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import urlopen
import os
from dotenv import load_dotenv
import requests

import config

load_dotenv()

API_KEY = os.getenv("OPENWA_API_KEY")
SESSION_ID = os.getenv("OPENWA_SESSION_ID")
OPENWA_API_URL = os.getenv("OPENWA_API_URL")

# Horário de Brasília/Recife (sem horário de verão desde 2019)
FUSO_LOCAL = timezone(timedelta(hours=-3))

STATUS_TEM_AGUA = "tem_agua"
STATUS_ULTIMO_DIA = "ultimo_dia"
STATUS_SEM_AGUA = "sem_agua"

MENSAGENS_STATUS = {
	STATUS_TEM_AGUA: "Hoje tem água! 💧",
	STATUS_ULTIMO_DIA: "Hoje é o último dia! ⚠️",
	STATUS_SEM_AGUA: "Hoje não tem água! 🚱",
}


def epoch_para_data_hora(timestamp):
	"""Converte epoch em milissegundos para data e hora UTC."""
	if timestamp is None:
		return None
	return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).strftime(
		"%d/%m/%Y %H:%M:%S"
	)


def epoch_para_data(timestamp):
	"""Converte epoch em milissegundos para a data do calendário.

	A API grava cada dia como meia-noite (ou 05:00) em UTC, então a data UTC
	é o dia correto do calendário.
	"""
	return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).date()


def periodos_validos(periodos):
	"""Descarta períodos sem início/término ou com término antes do início."""
	return [
		periodo
		for periodo in periodos
		if periodo.get("inicio") is not None
		and periodo.get("termino") is not None
		and periodo["inicio"] <= periodo["termino"]
	]


def periodos_que_contem_data(data_hora, periodos):
	"""Retorna os períodos que incluem o dia informado, inclusive o primeiro e o último dia."""
	dia = data_hora.astimezone(FUSO_LOCAL).date()
	return [
		periodo
		for periodo in periodos_validos(periodos)
		if epoch_para_data(periodo["inicio"]) <= dia <= epoch_para_data(periodo["termino"])
	]


def eh_ultimo_dia_do_periodo(data_hora, periodos):
	"""Retorna True quando o dia informado é o último dia de algum período."""
	dia = data_hora.astimezone(FUSO_LOCAL).date()
	return any(
		epoch_para_data(periodo["termino"]) == dia
		for periodo in periodos_validos(periodos)
	)


def status_do_dia(data_hora, periodos):
	"""Classifica o dia: último dia do período, dentro de um período ou sem água."""
	if eh_ultimo_dia_do_periodo(data_hora, periodos):
		return STATUS_ULTIMO_DIA
	if periodos_que_contem_data(data_hora, periodos):
		return STATUS_TEM_AGUA
	return STATUS_SEM_AGUA


def montar_url(mes, ano):
	url_base = (
		"https://geo.compesa.com.br:6443/arcgis/rest/services/Calendario/"
		"Calendario/MapServer/5/query"
	)
	parametros = {
		"_": "1790122816081",
		"f": "json",
		"where": (
			f"(ID='TM1') AND (DATEPART(MONTH,Inicio)='{mes:02d}' "
			f"OR DATEPART(MONTH,Termino)='{mes:02d}') AND "
			f"(DATEPART(YEAR,Inicio)='{ano}' OR DATEPART(YEAR,Termino)='{ano}')"
		),
		"returnGeometry": "false",
		"spatialRel": "esriSpatialRelIntersects",
		"outFields": "Inicio,Termino,colapso",
	}
	return f"{url_base}?{urlencode(parametros)}"


def consultar_periodos(mes, ano):
	url = montar_url(mes, ano)
	with urlopen(url, timeout=30) as resposta:
		dados = json.load(resposta)

	if "error" in dados:
		raise RuntimeError(f"Erro retornado pela API: {dados['error']}")

	periodos = [
		{
			"inicio": feature.get("attributes", {}).get("Inicio"),
			"termino": feature.get("attributes", {}).get("Termino"),
			"colapso": feature.get("attributes", {}).get("colapso"),
		}
		for feature in dados.get("features", [])
	]
	return mes, ano, periodos


def main():
	# consultar mes e ano atual
	mes_atual = datetime.now(FUSO_LOCAL).month
	ano_atual = datetime.now(FUSO_LOCAL).year

	periodos = consultar_periodos(mes_atual, ano_atual)

	if not periodos[2]:
		print("Nenhum período encontrado.")
		return

	periodos_formatados = []

	for numero, periodo in enumerate(periodos[2], start=1):
		inicio = epoch_para_data_hora(periodo["inicio"])
		termino = epoch_para_data_hora(periodo["termino"])
		colapso = periodo["colapso"]
		periodos_formatados.append(f"🔹{inicio} → {termino}")

	url = f"{OPENWA_API_URL}/api/sessions/{SESSION_ID}/start"

	payload = {}
	headers = {
	'Accept': 'application/json',
	'X-API-Key': API_KEY
	}

	response = requests.request("POST", url, headers=headers, data=payload)

	print(response.text)
	# obter nome do mes com o numero
	nome_mes = {
		1: "JANEIRO",
		2: "FEVEREIRO",
		3: "MARÇO",
		4: "ABRIL",
		5: "MAIO",
		6: "JUNHO",
		7: "JULHO",
		8: "AGOSTO",
		9: "SETEMBRO",
		10: "OUTUBRO",
		11: "NOVEMBRO",
		12: "DEZEMBRO"
	}.get(mes_atual, f"MÊS {mes_atual:02d}")

	# verificar se hoje tem água, se é o último dia ou se não tem água
	data_hoje = datetime.now(FUSO_LOCAL)
	status_hoje = MENSAGENS_STATUS[status_do_dia(data_hoje, periodos[2])]

	mensagem_datas = "\n".join(periodos_formatados)

	mensagem = f"""
📅 CALENDÁRIO DE ABASTECIMENTO DE ÁGUA
{nome_mes} DE {ano_atual}

{mensagem_datas}


{status_hoje}
	"""
	print(mensagem)

	for destinatario in config.DESTINATARIOS:
		url = f"{OPENWA_API_URL}/api/sessions/{SESSION_ID}/messages/send-text"

		payload = json.dumps({
		"chatId": destinatario,
		"text": mensagem,
		})
		headers = {
		'Content-Type': 'application/json',
		'Accept': 'application/json',
		'X-API-Key': API_KEY
		}

		response = requests.request("POST", url, headers=headers, data=payload)

		print(response.text)


if __name__ == "__main__":
	main()
