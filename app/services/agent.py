"""The agent loop: ask the model, run the tools it picks, send results back, repeat."""
import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.services.tools import make_tools
from app.utils.llm import llm

MAX_STEPS = 6

SYSTEM_PROMPT = '''You are PayPilot, a friendly shopping and order assistant for a small electronics store.
Rules:
- Use tools for everything. Never invent products, prices, orders or payment results.
- Browse: search_products. Cart: add_to_cart, remove_from_cart, view_cart. Orders: place_order, list_orders, get_order.
- Pay: checkout. Cancel or refund: cancel_order. Questions about how orders, payment or refunds work: order_help.
- When the user selects several products, pass all their ids in one call. When they say this or it, leave ids empty.
- Use separate=true only when the user wants one order per product. Otherwise several products become one multi order.
- If a tool returns needs_confirmation, say exactly what will be paid or refunded (with the order ids and total) and ask the user to reply yes. When they reply yes, call checkout with order_ids, or cancel_order again with the same order_ids.
- If checkout returns approval_needed, say the total and ask them to approve it in the PayPal window.
- Say a payment or refund succeeded ONLY if the tool result says paid or refunded.
- Quote order ids exactly as given, like ORD-1. Keep replies short (1-3 sentences). Product and order cards are shown separately.
'''


def confirm_hint(session):
    '''If a confirmation is waiting and this message is the very next one, remind the model what to do.'''
    pend = session['pending_confirm']
    if not pend or session['turn'] != pend['turn'] + 1:
        return ''
    key = pend['key']
    ids = ', '.join(key['ids'])
    tool_name = 'checkout' if key['action'] == 'pay' else 'cancel_order'
    return ('\nA confirmation is waiting: ' + key['action'] + ' ' + ids + ' for ' + key['total'] + '. '
            'If the user says yes, call ' + tool_name + ' with order_ids=[' + ids + ']. '
            'If the user says no or changes the subject, do not call any payment or refund tool.')


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(p.get('text', '') if isinstance(p, dict) else str(p) for p in content)
    return str(content or '')


def to_messages(history):
    out = []
    for m in history:
        cls = HumanMessage if m['role'] == 'user' else AIMessage
        out.append(cls(content=m['content']))
    return out


async def run_agent(session, message):
    session['turn'] += 1
    ui = {'products': None, 'order': None, 'payment': None, 'confirm': None, 'touched': None}
    tools = make_tools(session, ui)
    tool_map = {t.name: t for t in tools}
    model = llm.bind_tools(tools)

    messages = [SystemMessage(content=SYSTEM_PROMPT + confirm_hint(session))]
    messages += to_messages(session['history'][-12:])
    messages.append(HumanMessage(content=message))

    reply = 'Sorry, I got stuck. Could you try again?'
    for _ in range(MAX_STEPS):
        try:
            ai = await model.ainvoke(messages)
        except Exception as e:
            print('LLM error:', repr(e))
            reply = 'Sorry, the AI service had a problem (' + type(e).__name__ + '). Please try again.'
            break
        messages.append(ai)
        if not ai.tool_calls:
            reply = text_of(ai.content)
            break
        for call in ai.tool_calls:
            fn = tool_map.get(call['name'])
            result = await fn.ainvoke(call['args']) if fn else json.dumps({'error': 'Unknown tool'})
            messages.append(ToolMessage(content=str(result), tool_call_id=call['id']))

    session['history'] += [
        {'role': 'user', 'content': message},
        {'role': 'assistant', 'content': reply},
    ]
    session['history'] = session['history'][-20:]
    return {'reply': reply, **ui}
