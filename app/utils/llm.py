from langchain_groq import ChatGroq

from app.utils.config import GROQ_API_KEY, GROQ_MODEL

if not GROQ_API_KEY:
    raise RuntimeError('GROQ_API_KEY not found. Set it in backend/.env (or in the Render dashboard).')

llm = ChatGroq(model=GROQ_MODEL, temperature=0, api_key=GROQ_API_KEY)


def test():
    return llm.invoke('what is rag.').content
