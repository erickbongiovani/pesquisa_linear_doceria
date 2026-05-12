from flask import render_template, redirect, session
import os
from functools import wraps

def brl(value):
    '''Format value as BRL.'''
    if value is None:
        return 'R$ 0,00'
    valor_formatado = f'{value:,.2f}'
    valor_br = valor_formatado.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {valor_br}'

def apology(message, code=400):
    """Renderiza mensagem de erro (pode usar o padrão do CS50)."""
    return render_template("apology.html", top=code, bottom=message), code

def login_required(f):
    """Decorador para exigir login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function
