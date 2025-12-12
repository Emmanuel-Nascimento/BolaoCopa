from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from datetime import datetime
import uuid 

app = Flask(__name__)

# --- CONFIGURAÇÕES GERAIS ---
app.config['SECRET_KEY'] = 'chave_secreta_do_bolao_123' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

# --- CONFIGURAÇÕES DO GMAIL (PREENCHA AQUI!) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'emmanuel.nascimento19@gmail.com'  # <--- SEU EMAIL
app.config['MAIL_PASSWORD'] = 'roir usqg ojlz ktlq'     # <--- SUA SENHA DE APP

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login' 

# --- DADOS ---
DICIONARIO_TIMES = {
    "Alemanha": "de", "Arábia Saudita": "sa", "Argentina": "ar", "Austrália": "au", 
    "Bélgica": "be", "Brasil": "br", "Camarões": "cm", "Canadá": "ca", "Catar": "qa", 
    "Coreia do Sul": "kr", "Costa Rica": "cr", "Croácia": "hr", "Dinamarca": "dk", 
    "Equador": "ec", "Espanha": "es", "Estados Unidos": "us", "França": "fr", 
    "Gana": "gh", "Holanda": "nl", "Inglaterra": "gb-eng", "Irã": "ir", "Japão": "jp", 
    "Marrocos": "ma", "México": "mx", "País de Gales": "gb-wls", "Polônia": "pl", 
    "Portugal": "pt", "Senegal": "sn", "Sérvia": "rs", "Suíça": "ch", 
    "Tunísia": "tn", "Uruguai": "uy"
}
TIMES_MUNDIAIS = sorted(DICIONARIO_TIMES.keys())

# --- MODELOS ---

class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(100), nullable=False)
    pontos = db.Column(db.Integer, default=0)
    is_admin = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(100))
    palpites = db.relationship('Palpite', backref='usuario', lazy=True)

class Jogo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time_a = db.Column(db.String(50), nullable=False)
    time_b = db.Column(db.String(50), nullable=False)
    data_hora = db.Column(db.DateTime, nullable=False)
    resultado_real = db.Column(db.String(10), default=None) 
    palpites = db.relationship('Palpite', backref='jogo', cascade="all, delete-orphan", lazy=True)

class Palpite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    id_jogo = db.Column(db.Integer, db.ForeignKey('jogo.id'), nullable=False)
    escolha = db.Column(db.String(10), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

def recalcular_ranking_geral():
    usuarios = Usuario.query.all()
    jogos_finalizados = Jogo.query.filter(Jogo.resultado_real != None).all()
    gabarito = {jogo.id: jogo.resultado_real for jogo in jogos_finalizados}

    for usuario in usuarios:
        pontos_novos = 0
        for palpite in usuario.palpites:
            resultado_do_jogo = gabarito.get(palpite.id_jogo)
            if resultado_do_jogo and palpite.escolha == resultado_do_jogo:
                pontos_novos += 1
        usuario.pontos = pontos_novos
    db.session.commit()

# --- ROTAS PRINCIPAIS ---

@app.route('/')
def index():
    jogos = Jogo.query.order_by(Jogo.data_hora).all()
    meus_palpites = {}
    agora = datetime.now()

    if current_user.is_authenticated:
        palpites_db = Palpite.query.filter_by(id_usuario=current_user.id).all()
        for p in palpites_db:
            meus_palpites[p.id_jogo] = p.escolha

    return render_template('index.html', jogos=jogos, meus_palpites=meus_palpites, bandeiras=DICIONARIO_TIMES, agora=agora)

@app.route('/ranking')
def ranking():
    usuarios = Usuario.query.order_by(Usuario.pontos.desc()).all()
    return render_template('ranking.html', usuarios=usuarios)

# --- LOGIN / CADASTRO / EMAIL ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and usuario.senha == senha:
            if not usuario.is_verified:
                flash('🔒 Conta não verificada! Verifique seu email.')
                return render_template('login.html')

            login_user(usuario)
            return redirect(url_for('index'))
        else:
            flash('Email ou senha incorretos!')
            
    return render_template('login.html')

@app.route('/reenviar_confirmacao', methods=['GET', 'POST'])
def reenviar_confirmacao():
    if request.method == 'POST':
        email = request.form.get('email')
        usuario = Usuario.query.filter_by(email=email).first()
        
        if usuario:
            if usuario.is_verified:
                flash('Sua conta já está verificada! Faça login.')
                return redirect(url_for('login'))
            
            token = uuid.uuid4().hex
            usuario.verification_token = token
            db.session.commit()
            
            try:
                msg = Message("Ativar Conta (Reenvio) - Bolão da Copa", 
                              sender=app.config['MAIL_USERNAME'], 
                              recipients=[email])
                link = url_for('confirmar_email', token=token, _external=True)
                msg.body = f"Link de ativação: {link}"
                mail.send(msg)
                flash('Novo link enviado! Verifique seu email.')
                return redirect(url_for('login'))
            except Exception as e:
                flash('Erro ao enviar email: ' + str(e))
        else:
            flash('Email não encontrado!')
            
    return render_template('reenviar_confirmacao.html')

@app.route('/esqueci_senha', methods=['GET', 'POST'])
def esqueci_senha():
    if request.method == 'POST':
        email = request.form.get('email')
        usuario = Usuario.query.filter_by(email=email).first()
        
        if usuario:
            token = uuid.uuid4().hex
            usuario.verification_token = token
            db.session.commit()
            
            try:
                msg = Message("Redefinir Senha - Bolão da Copa", 
                              sender=app.config['MAIL_USERNAME'], 
                              recipients=[email])
                link = url_for('resetar_senha', token=token, _external=True)
                msg.body = f"Clique para criar nova senha: {link}"
                mail.send(msg)
                flash('Link de recuperação enviado!')
                return redirect(url_for('login'))
            except Exception as e:
                flash('Erro ao enviar email: ' + str(e))
        else:
            flash('Email não encontrado!')
            
    return render_template('esqueci_senha.html')

@app.route('/resetar_senha/<token>', methods=['GET', 'POST'])
def resetar_senha(token):
    usuario = Usuario.query.filter_by(verification_token=token).first()
    
    if not usuario:
        flash('Link inválido ou expirado!')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        nova_senha = request.form.get('senha')
        usuario.senha = nova_senha
        usuario.verification_token = None
        db.session.commit()
        flash('Senha alterada! Faça login.')
        return redirect(url_for('login'))
        
    return render_template('resetar_senha.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if current_user.is_authenticated: return redirect(url_for('index'))
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        is_first_user = False
        if Usuario.query.count() == 0:
            is_first_user = True

        if Usuario.query.filter_by(email=email).first():
            flash('Este email já está cadastrado!')
        else:
            token = uuid.uuid4().hex
            novo_usuario = Usuario(
                nome=nome, 
                email=email, 
                senha=senha, 
                is_admin=is_first_user,
                is_verified=False,
                verification_token=token
            )
            db.session.add(novo_usuario)
            db.session.commit()

            try:
                msg = Message("Confirme seu Cadastro", 
                              sender=app.config['MAIL_USERNAME'], 
                              recipients=[email])
                link = url_for('confirmar_email', token=token, _external=True)
                msg.body = f"Clique para confirmar: {link}"
                mail.send(msg)
                flash('Cadastro realizado! Verifique seu email.')
            except Exception as e:
                flash(f'Erro ao enviar email: {str(e)}')
                db.session.delete(novo_usuario)
                db.session.commit()

            return redirect(url_for('login'))
            
    return render_template('cadastro.html')

@app.route('/confirmar/<token>')
def confirmar_email(token):
    usuario = Usuario.query.filter_by(verification_token=token).first()
    
    if usuario:
        if usuario.is_verified:
            flash('Conta já verificada. Faça login!')
        else:
            usuario.is_verified = True
            usuario.verification_token = None
            db.session.commit()
            flash('✅ Email confirmado! Pode logar.')
    else:
        flash('❌ Link inválido ou expirado.')
        
    return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ÁREA ADMIN ---

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.is_admin: 
        flash('Acesso negado!')
        return redirect(url_for('index'))

    if request.method == 'POST':
        if request.form.get('acao') == 'criar_jogo':
            time_a = request.form.get('time_a')
            time_b = request.form.get('time_b')
            data_string = request.form.get('data_hora') 
            try:
                data_formatada = datetime.strptime(data_string, '%Y-%m-%dT%H:%M')
                novo_jogo = Jogo(time_a=time_a, time_b=time_b, data_hora=data_formatada)
                db.session.add(novo_jogo)
                db.session.commit()
                flash('Jogo cadastrado!')
            except ValueError:
                flash('Erro na data!')

    jogos = Jogo.query.order_by(Jogo.data_hora).all()
    lista_usuarios = Usuario.query.all()
    lista_nomes = sorted(DICIONARIO_TIMES.keys())
    return render_template('admin.html', jogos=jogos, lista_usuarios=lista_usuarios, times=lista_nomes)

@app.route('/admin/resultado/<int:jogo_id>/<quem_ganhou>')
@login_required
def definir_resultado(jogo_id, quem_ganhou):
    if not current_user.is_admin: return redirect(url_for('index'))
    
    jogo = Jogo.query.get(jogo_id)
    if jogo:
        jogo.resultado_real = quem_ganhou
        db.session.commit()
        recalcular_ranking_geral()
        flash(f'Resultado atualizado!')
    return redirect(url_for('admin'))

@app.route('/admin/resetar_campeonato')
@login_required
def resetar_campeonato():
    if current_user.id != 1: return redirect(url_for('admin'))
        
    try:
        db.session.query(Palpite).delete()
        db.session.query(Jogo).delete()
        usuarios = Usuario.query.all()
        for u in usuarios: u.pontos = 0
        for u in usuarios:
            if u.id != 1: u.is_admin = False
        db.session.commit()
        flash('O Campeonato foi resetado!')
    except Exception as e:
        flash('Erro: ' + str(e))
    return redirect(url_for('admin'))

@app.route('/admin/toggle_admin/<int:user_id>')
@login_required
def toggle_admin(user_id):
    if current_user.id != 1: return redirect(url_for('admin'))
    if user_id == 1: return redirect(url_for('admin'))

    usuario = Usuario.query.get(user_id)
    if usuario:
        usuario.is_admin = not usuario.is_admin
        db.session.commit()
        flash(f'Permissão de {usuario.nome} alterada.')
    return redirect(url_for('admin'))

@app.route('/admin/deletar_usuario/<int:user_id>')
@login_required
def deletar_usuario(user_id):
    if current_user.id != 1: return redirect(url_for('admin'))
    if user_id == 1: return redirect(url_for('admin'))

    usuario = Usuario.query.get(user_id)
    if usuario:
        Palpite.query.filter_by(id_usuario=user_id).delete()
        db.session.delete(usuario)
        db.session.commit()
        flash('Usuário removido.')
    return redirect(url_for('admin'))

@app.route('/admin/editar_jogo/<int:jogo_id>', methods=['GET', 'POST'])
@login_required
def editar_jogo(jogo_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    
    jogo = Jogo.query.get(jogo_id)
    if request.method == 'POST':
        jogo.time_a = request.form.get('time_a')
        jogo.time_b = request.form.get('time_b')
        data_string = request.form.get('data_hora')
        try:
            jogo.data_hora = datetime.strptime(data_string, '%Y-%m-%dT%H:%M')
            db.session.commit()
            flash('Jogo atualizado!')
            return redirect(url_for('admin'))
        except ValueError:
            flash('Erro na data.')

    lista_nomes = sorted(DICIONARIO_TIMES.keys())
    return render_template('editar_jogo.html', jogo=jogo, times=lista_nomes)

@app.route('/admin/deletar_jogo/<int:jogo_id>')
@login_required
def deletar_jogo(jogo_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    jogo = Jogo.query.get(jogo_id)
    if jogo:
        db.session.delete(jogo)
        db.session.commit()
        recalcular_ranking_geral()
        flash('Jogo removido.')
    return redirect(url_for('admin'))

@app.route('/admin/editar_usuario/<int:user_id>', methods=['GET', 'POST'])
@login_required
def editar_usuario(user_id):
    if user_id == 1 and current_user.id != 1: return redirect(url_for('admin'))
    pode_editar = current_user.is_admin or (current_user.id == user_id)
    if not pode_editar: return redirect(url_for('index'))
    
    usuario = Usuario.query.get(user_id)
    if request.method == 'POST':
        usuario.nome = request.form.get('nome')
        db.session.commit()
        flash('Nome alterado!')
        return redirect(url_for('admin' if current_user.is_admin else 'index'))
        
    return render_template('editar_usuario.html', usuario=usuario)

@app.route('/palpitar/<int:jogo_id>/<escolha>')
@login_required
def palpitar(jogo_id, escolha):
    jogo = Jogo.query.get(jogo_id)
    if not jogo: return redirect(url_for('index'))
    if jogo.resultado_real: return redirect(url_for('index'))
    if datetime.now() > jogo.data_hora: return redirect(url_for('index'))

    palpite_existente = Palpite.query.filter_by(id_usuario=current_user.id, id_jogo=jogo_id).first()
    if palpite_existente:
        palpite_existente.escolha = escolha
    else:
        novo_palpite = Palpite(id_usuario=current_user.id, id_jogo=jogo_id, escolha=escolha)
        db.session.add(novo_palpite)
    db.session.commit()
    recalcular_ranking_geral()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # OTIMIZAÇÃO: Debug=False para produção (site mais rápido)
    app.run(debug=False)