from flask import Flask, render_template, request, redirect, send_file, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired, Email
from datetime import datetime
from flask_moment import Moment
from flask_migrate import Migrate
import flask_excel as excel
from io import BytesIO
import pandas as pd
import secrets
import os


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///checks.db'
db = SQLAlchemy(app)
moment = Moment(app)
migrate = Migrate(app, db, render_as_batch=True)
secret = secrets.token_urlsafe(32)
app.secret_key = secret
PIN_CODE = os.environ.get('PIN_CODE', '2948')


def login_required(view_func):
    def wrapper(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return view_func(*args, **kwargs)
    wrapper.__name__=view_func.__name__
    return wrapper



class Checks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(40), nullable=False)
    summ = db.Column(db.Integer)
    
    
    
class Categories(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    naming = db.Column(db.String(40), nullable=False)
    
    

class Operations(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    summa = db.Column(db.Integer)
    comment = db.Column(db.String(100))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    check_id = db.Column(db.Integer)
    check_name = db.Column(db.String(40))
    categ_id = db.Column(db.String(40))
    
    

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        pin = request.form.get('pin', '').strip()
        if pin == PIN_CODE:
            session['authenticated'] = True
            return redirect('/')
        else:
            error = "Неверный пин-код!"
    return render_template('login.html', error=error)



@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))



@app.route("/", methods=['POST', 'GET'])
@login_required
def index():
    allchecks = Checks.query.all()
    if request.method == 'POST':
        title = request.form['title']
        errors = []
        if not title:
            errors.append('Название счета не может быть пустым')
        if errors:
            for error in errors:
                flash(error)
            return redirect(url_for('index'))
        check = Checks(title=title, summ=0)
        try:
            db.session.add(check)
            db.session.commit()
            return redirect('/')
        except:
            return 'При добавлении счета произошла ошибка!' 
    else:
        return render_template('index.html', allchecks=allchecks)
    
    
   
@app.route("/categories/", methods=['POST', 'GET'])
@login_required 
def categories():
    allcateg = Categories.query.all()
    if request.method == 'POST':
        naming = request.form['categori']
        errors = []
        if not naming:
            errors.append('Название категории не может быть пустым!')
        if errors:
            for error in errors:
                flash(error)
            return redirect(url_for('categories'))
        categ = Categories(naming=naming)
        try:
            db.session.add(categ)
            db.session.commit()
            return redirect('/categories/')
        except:
            return 'При добавлении категории произошла ошибка!'
    else:
        return render_template('categories.html', allcateg=allcateg)
    
    
    
@app.route('/checks/<int:id>', methods=['POST', 'GET'])
@login_required
def checks_id(id):
    allcheck = Checks.query.get(id)
    allopp = Operations.query.order_by(Operations.date.desc()).all()
    allcateg = Categories.query.all()
    if request.method == 'POST':
        summa = request.form['summ_op']
        comment = request.form['comm_op']
        categ = request.form['categories']
        check_name = allcheck.title
        errors = []
        if not summa:
            errors.append('Сумма не может быть никакой, лол')
        if errors:
            for error in errors:
                flash(error)
            return redirect(f'/checks/{id}')
        oper = Operations(summa=summa, comment=comment, check_id=id, check_name=check_name, categ_id=categ)
        allcheck.summ += int(summa)
        try:
            db.session.add(oper)
            db.session.commit()
            return redirect(f'/checks/{id}')
        except:
            return render_template('Не удалось добавить транзакцию')
    else:
        return render_template('check.html', allcheck=allcheck, allopp=allopp, allcateg=allcateg)



@app.route('/oper/<int:id>/del')
@login_required
def oper_delete(id):
    allop = Operations.query.get_or_404(id)
    checkel = Checks.query.get(allop.check_id)
    try:
        db.session.delete(allop)
        checkel.summ -= allop.summa
        db.session.commit()
        return redirect(f'/checks/{checkel.id}')
    except:
        return "При удалении счета произошла ошибка"



@app.route('/checks/<int:id>/del')
@login_required
def checks_delete(id):
    allcheck = Checks.query.get_or_404(id)
    allop = Operations.query.all()
    try:
        for i in allop:
            if i.check_id == id:
                db.session.delete(i)
        db.session.delete(allcheck)
        db.session.commit()
        return redirect('/')
    except:
        return "При удалении счета произошла ошибка"
    
   
    
@app.route('/categ/<int:id>/del')
@login_required   
def categ_delete(id):
    allcateg = Categories.query.get_or_404(id)
    allopp = Operations.query.all()
    try:
        for i in allopp:
            if i.categ_id == allcateg.naming:
                i.categ_id = "Без категории"
        db.session.delete(allcateg)
        db.session.commit()
        return redirect('/categories/')
    except:
        return "При удалении категории произошла ошибка"
    
    
    
@app.route('/oper/<int:id>/', methods=['POST', 'GET'])
@login_required
def oper_id(id):
    allopp = Operations.query.get(id)
    checkelem = Checks.query.get(allopp.check_id)
    allcateg = Categories.query.all()
    n = allopp.summa
    
    if request.method == 'POST':
        checkelem.summ -= n
        allopp.summa = request.form['summ_up']
        allopp.comment = request.form['comment_up']
        allopp.categ_id = request.form['categories']
        checkelem.summ += int(request.form['summ_up'])
        try:
            db.session.commit()
            return redirect(f'/oper/{id}')
        except:
            return render_template('Не удалось редактировать транзакцию')
    else:
        return render_template('operation.html', allopp=allopp, checkelem=checkelem, allcateg=allcateg)
    


@app.route('/categ/<int:id>', methods=['POST', 'GET'])
@login_required
def categ(id):
    allcateg = Categories.query.get(id)
    allopp = Operations.query.order_by(Operations.date.desc()).all()
    allcheck = Checks.query.all()
    if request.method == 'POST':
        allcateg.naming = request.form['name']
        for i in allopp:
            i.categ_id = allcateg.naming
        try:
            db.session.commit()
            return redirect(f'/categ/{id}')
        except:
            return 'Не удалось редактировать категорию'
    
    return render_template('categ.html', allcateg=allcateg, allopp=allopp, allcheck=allcheck)



@app.route('/download/')
@login_required
def download():
    opers = Operations.query.all()
    data = [{'№': oper.id, 'Сумма': oper.summa, 'Комментарий': oper.comment, 'Дата': oper.date, 'Счет': oper.check_name, 'Категория': oper.categ_id}
            for oper in opers]
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Операции')
    
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='Операции.xlsx')


    
    
    



if __name__ == '__main__':
    app.run(debug=True, port=5000)
    