"""Orquestacion de una conversacion con el asistente.

La conversacion no se guarda en la base: el cliente (Angular o Flutter) manda
los ultimos mensajes en cada pedido. Mantiene la app sin tablas propias, que es
lo que permite retirarla sin dejar rastro si se elige otro enfoque.
"""

from django.utils import timezone

from . import llm, tools

# Rondas maximas de herramientas por mensaje. Cada ronda es una llamada al
# proveedor y gasta cuota: dos alcanzan para "buscar" y luego "ver detalle".
MAX_TOOL_ROUNDS = 3

SYSTEM_PROMPT = """Eres "Situr", el asistente turístico virtual de SITUR-SMART, una plataforma de turismo en Bolivia.

Reglas:
- Responde siempre en español, de forma breve, cálida y clara (máximo 6 oraciones o una lista corta).
- Solo hablas de turismo en Bolivia y de los servicios de SITUR-SMART. Si te preguntan otra cosa, indica amablemente que solo puedes ayudar con viajes y hospedajes.
- NUNCA inventes hoteles, precios, habitaciones ni disponibilidad. Para cualquier dato de hospedajes usa las herramientas. Si la herramienta no devuelve resultados, dilo y sugiere ajustar ciudad, presupuesto o fechas.
- Al recomendar, menciona el nombre, la ciudad, el precio "desde" con su moneda y uno o dos motivos de la recomendación.
- Puedes dar consejos generales de viaje en Bolivia (clima, altura, qué llevar), aclarando que son orientativos.
- No pidas ni repitas datos personales (documentos, tarjetas, contraseñas).
- Todavía no puedes hacer reservas: indica que el viajero puede abrir el hospedaje en el Marketplace para ver detalles.
Fecha de hoy: {hoy}."""


def _history(messages: list[dict]) -> list[dict]:
    """Traduce el historial del cliente al formato del proveedor.

    Solo se aceptan los roles usuario/asistente: un cliente no puede inyectar
    mensajes de sistema ni resultados de herramientas falsos.
    """
    role_map = {"usuario": "user", "asistente": "assistant"}
    return [
        {"role": role_map[item["rol"]], "content": item["contenido"]}
        for item in messages
        if item.get("rol") in role_map and item.get("contenido")
    ]


def reply(*, message: str, history: list[dict]) -> dict:
    """Responde un mensaje y devuelve el texto y los hospedajes mencionados."""
    conversation = [
        {"role": "system", "content": SYSTEM_PROMPT.format(hoy=timezone.localdate().isoformat())},
        *_history(history),
        {"role": "user", "content": message},
    ]
    cards: dict[int, dict] = {}

    for _ in range(MAX_TOOL_ROUNDS):
        answer = llm.chat(conversation, tools=tools.DEFINITIONS)
        tool_calls = answer.get("tool_calls") or []
        if not tool_calls:
            break
        conversation.append(
            {"role": "assistant", "content": answer.get("content") or "", "tool_calls": tool_calls}
        )
        for call in tool_calls:
            function = call.get("function") or {}
            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id", ""),
                    "content": tools.run(function.get("name", ""), function.get("arguments"), cards),
                }
            )
    else:
        # Agoto las rondas pidiendo herramientas: se fuerza una respuesta final
        # sin ellas para no devolver un texto vacio.
        answer = llm.chat(conversation)

    text = (answer.get("content") or "").strip()
    if not text:
        text = "No pude generar una respuesta. ¿Puedes reformular tu pregunta?"
    return {"respuesta": text, "hospedajes": list(cards.values())}
