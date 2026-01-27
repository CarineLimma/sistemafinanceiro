from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from functools import wraps
from dotenv import load_dotenv
import sqlite3
from datetime import datetime, timedelta
import os
from io import BytesIO
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Table


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')
app.permanent_session_lifetime = timedelta(days=7)

app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
app.config['MAIL_MAX_EMAILS'] = None
app.config['MAIL_SUPPRESS_SEND'] = False

mail = Mail(app)
serializer = URLSafeTimedSerializer(app.secret_key)

@app.template_filter('datetimeformat')
def datetimeformat(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').strftime('%d/%m/%Y')
    except Exception:
        return value

def init_db():
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                descricao TEXT NOT NULL,
                valor REAL NOT NULL,
                data TEXT NOT NULL,
                categoria TEXT NOT NULL,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transacoes_recorrentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                descricao TEXT NOT NULL,
                valor REAL NOT NULL,
                categoria TEXT,
                data_inicio TEXT NOT NULL,
                frequencia TEXT NOT NULL,
                repeticoes INTEGER NOT NULL,
                ativo INTEGER DEFAULT 1,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
            )
        ''')

        conn.commit()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']

        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, senha FROM usuarios WHERE email = ?", (email,))
            user = cursor.fetchone()

            if user and check_password_hash(user[1], senha):
                session['usuario_id'] = user[0]
                flash("Login realizado com sucesso!", "success")
                return redirect(url_for('dashboard'))
            else:
                flash("Usuário ou senha incorretos.", "danger")

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']

        if not nome or not email or not senha:
            flash('Por favor, preencha todos os campos.', 'danger')
            return redirect(url_for('register'))

        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM usuarios WHERE email = ?', (email,))
            usuario_existente = cursor.fetchone()

            if usuario_existente:
                flash('E-mail já cadastrado. Faça login ou use outro e-mail.', 'warning')
                return redirect(url_for('register'))

            senha_criptografada = generate_password_hash(senha)
            cursor.execute('INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)',
                           (nome, email, senha_criptografada))
            conn.commit()

        flash('Cadastro realizado com sucesso. Faça login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/agendar', methods=['GET', 'POST'])
@login_required
def agendar_transacao():
    if request.method == 'POST':
        tipo = request.form['tipo']
        descricao = request.form['descricao']
        try:
            valor = float(request.form['valor'])
        except ValueError:
            flash("Valor inválido.", "danger")
            return redirect(url_for('agendar_transacao'))
        categoria = request.form['categoria']
        data_inicio = request.form['data_inicio']
        frequencia = request.form['frequencia']
        try:
            repeticoes = int(request.form['repeticoes'])
        except ValueError:
            flash("Número de repetições inválido.", "danger")
            return redirect(url_for('agendar_transacao'))

        usuario_id = session['usuario_id']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO transacoes_recorrentes (
                usuario_id, tipo, descricao, valor, categoria,
                data_inicio, frequencia, repeticoes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            usuario_id, tipo, descricao, valor, categoria,
            data_inicio, frequencia, repeticoes
        ))
        conn.commit()
        conn.close()

        flash('Transação recorrente agendada com sucesso!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('agendar_transacao.html')


@app.route('/dashboard')
@login_required
def dashboard():
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        flash("Usuário não autenticado.")
        return redirect(url_for('login'))

    try:
        hoje = datetime.now()
        meses_ano = []
        labels_meses = []

        for i in range(11, -1, -1):
            mes_corrente = hoje.replace(day=1) - timedelta(days=30*i)
            ano = mes_corrente.year
            mes = mes_corrente.month
            meses_ano.append(f"{ano:04d}-{mes:02d}")
            labels_meses.append(f"{mes:02d}/{ano:04d}")

        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT nome FROM usuarios WHERE id = ?", (usuario_id,))
            resultado = cursor.fetchone()
            nome = resultado[0] if resultado and resultado[0] else "Usuário"

            cursor.execute(
                "SELECT SUM(valor) FROM transacoes WHERE usuario_id = ? AND tipo = 'receita'",
                (usuario_id,)
            )
            total_receitas = cursor.fetchone()[0] or 0

            cursor.execute(
                "SELECT SUM(valor) FROM transacoes WHERE usuario_id = ? AND tipo = 'despesa'",
                (usuario_id,)
            )
            total_despesas = cursor.fetchone()[0] or 0

            cursor.execute("""
                SELECT strftime('%Y-%m', data) AS ym, SUM(valor)
                FROM transacoes
                WHERE usuario_id = ? AND tipo = 'receita'
                GROUP BY ym
            """, (usuario_id,))
            receitas_por_mes = dict(cursor.fetchall())

            cursor.execute("""
                SELECT strftime('%Y-%m', data) AS ym, SUM(valor)
                FROM transacoes
                WHERE usuario_id = ? AND tipo = 'despesa'
                GROUP BY ym
            """, (usuario_id,))
            despesas_por_mes = dict(cursor.fetchall())

        valores_receitas = [float(receitas_por_mes.get(m, 0)) for m in meses_ano]
        valores_despesas = [float(despesas_por_mes.get(m, 0)) for m in meses_ano]

        return render_template(
            'dashboard.html',
            nome=nome,
            total_receitas=total_receitas,
            total_despesas=total_despesas,
            labels_meses=labels_meses[::-1], 
            valores_receitas=valores_receitas[::-1],
            valores_despesas=valores_despesas[::-1]
        )

    except Exception as e:
        flash(f"Erro ao carregar o dashboard: {str(e)}", "danger")
        return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    session.pop('usuario_id', None)
    flash("Logout realizado com sucesso.", "success")
    return redirect(url_for('login'))

@app.route('/receita', methods=['GET', 'POST'])
@login_required
def adicionar_receita():
    if request.method == 'POST':
        descricao = request.form['descricao']
        valor_str = request.form['valor']
        data = request.form['data']
        categoria = request.form['categoria']
        usuario_id = session['usuario_id']

        try:
            valor = float(valor_str)
        except ValueError:
            flash("Valor inválido. Digite um número válido.", "danger")
            return redirect(url_for('adicionar_receita'))

        try:
            datetime.strptime(data, '%Y-%m-%d')  # verifica formato
        except ValueError:
            flash("Data inválida. Escolha uma data válida no formato correto.", "danger")
            return redirect(url_for('adicionar_receita'))

        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transacoes (usuario_id, tipo, descricao, valor, data, categoria)
                VALUES (?, 'receita', ?, ?, ?, ?)
            ''', (usuario_id, descricao, valor, data, categoria))
            conn.commit()

        flash('Receita adicionada com sucesso!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('adicionar_receita.html')

@app.route('/despesa', methods=['GET', 'POST'])
@login_required
def adicionar_despesa():
    if request.method == 'POST':
        descricao = request.form['descricao']
        valor_str = request.form['valor']
        data = request.form['data']
        categoria = request.form['categoria']
        usuario_id = session['usuario_id']

        try:
            valor = float(valor_str)
        except ValueError:
            flash("Valor inválido. Digite um número válido.", "danger")
            return redirect(url_for('adicionar_despesa'))

        try:
            datetime.strptime(data, '%Y-%m-%d')
        except ValueError:
            flash("Data inválida. Escolha uma data válida no formato correto.", "danger")
            return redirect(url_for('adicionar_despesa'))

        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transacoes (usuario_id, tipo, descricao, valor, data, categoria)
                VALUES (?, 'despesa', ?, ?, ?, ?)
            ''', (usuario_id, descricao, valor, data, categoria))
            conn.commit()

        flash('Despesa adicionada com sucesso!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('adicionar_despesa.html')

@app.route('/historico')
@login_required
def historico():
    usuario_id = session['usuario_id']

    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tipo, descricao, valor, data, categoria FROM transacoes
            WHERE usuario_id = ? ORDER BY data DESC
        """, (usuario_id,))
        transacoes = cursor.fetchall()

        cursor.execute("SELECT nome FROM usuarios WHERE id = ?", (usuario_id,))
        nome_res = cursor.fetchone()
        nome = nome_res[0] if nome_res else "Usuário"

    return render_template('historico.html', transacoes=transacoes, nome=nome)

@app.route('/exportar_excel')
@login_required
def exportar_excel():
    usuario_id = session['usuario_id']
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT data, tipo, categoria, descricao, valor
        FROM transacoes
        WHERE usuario_id = ?
        ORDER BY data DESC
    """, (usuario_id,))
    dados = cursor.fetchall()
    conn.close()

    if not dados:
        flash("Nenhuma transação encontrada para exportar.", "info")
        return redirect(url_for('dashboard'))

    colunas = ['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor']
    df = pd.DataFrame(dados, columns=colunas)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Transações')

    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='historico_transacoes.xlsx'
    )

@app.route('/exportar_pdf')
@login_required
def exportar_pdf():
    usuario_id = session['usuario_id']

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT tipo, categoria, valor, data, descricao FROM transacoes WHERE usuario_id = ?", (usuario_id,))
    transacoes = cursor.fetchall()
    conn.close()

    if not transacoes:
        flash("Nenhuma transação encontrada para exportar.", "info")
        return redirect(url_for('dashboard'))

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)

    data = [['Tipo', 'Categoria', 'Valor (R$)', 'Data', 'Descrição']]

    for t in transacoes:
        tipo, categoria, valor, data_str, descricao = t
        data_br = datetime.strptime(data_str, '%Y-%m-%d').strftime('%d/%m/%Y')
        data.append([tipo, categoria, f"R$ {valor:.2f}", data_br, descricao])

    table = Table(data)
    elementos = [table]
    doc.build(elementos)

    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name='transacoes.pdf', mimetype='application/pdf')

@app.route('/redefinir-senha/<token>', methods=['GET', 'POST'])
def redefinir_senha(token):
    try:
        email = serializer.loads(token, salt='senha-recuperacao', max_age=3600)
    except SignatureExpired:
        flash("O link expirou. Solicite um novo e-mail.", "danger")
        return redirect(url_for('esqueci_senha'))
    except BadSignature:
        flash("Link inválido.", "danger")
        return redirect(url_for('esqueci_senha'))


    if request.method == 'POST':
        senha = request.form.get('senha')
        senha_confirm = request.form.get('senha_confirm')

        if senha != senha_confirm:
            flash("As senhas não coincidem.", "danger")
            return render_template('redefinir_senha.html', token=token)

        nova_senha = generate_password_hash(senha)

        try:
            with sqlite3.connect('database.db') as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
                user = cursor.fetchone()

                if user:
                    cursor.execute("UPDATE usuarios SET senha = ? WHERE email = ?", (nova_senha, email))
                    conn.commit()

            flash("Senha redefinida com sucesso! Faça login.", "success")
            return redirect(url_for('login'))

        except Exception as e:
            print("Erro ao atualizar senha:", e)
            flash("Ocorreu um erro. Tente novamente.", "danger")
            return render_template('redefinir_senha.html', token=token)

    return render_template('redefinir_senha.html', token=token)
@app.route('/esqueci-senha', methods=['GET', 'POST'])
def esqueci_senha():
    if request.method == 'POST':
        email = request.form.get('email')

        try:
            with sqlite3.connect('database.db') as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS password_resets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL,
                        token TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
                usuario = cursor.fetchone()

                if not usuario:
                    flash("E-mail não encontrado no sistema.", "danger")
                    return redirect(url_for('esqueci_senha'))

                token = serializer.dumps(email, salt='senha-recuperacao')

                cursor.execute("INSERT INTO password_resets (email, token) VALUES (?, ?)", (email, token))
                conn.commit()

            link_redefinicao = url_for('redefinir_senha', token=token, _external=True)

            msg = Message("Recuperação de Senha - Sistema Financeiro",
                          recipients=[email])
            msg.body = f"Clique no link para redefinir sua senha: {link_redefinicao}"
            mail.send(msg)

            flash("E-mail enviado com instruções para redefinição de senha.", "success")
            return redirect(url_for('login'))

        except Exception as e:
            print(f"Erro no esqueci_senha: {e}")  # Log no console do Render
            flash("Ocorreu um erro interno. Tente novamente mais tarde.", "danger")
            return redirect(url_for('esqueci_senha'))

    return render_template('esqueci_senha.html')

if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
