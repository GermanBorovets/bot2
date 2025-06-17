from flask import Flask, render_template, request, redirect, send_file, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_moment import Moment
from io import BytesIO
import pandas as pd
import secrets
import openpyxl
import os
import psycopg2
from dotenv import load_dotenv
from sqlalchemy import extract, func, desc


# Загрузка переменных окружения ДО создания приложения
load_dotenv()


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://gen_user::\yB4|c~TFuxQf@185.178.46.109:5432/default_db'
db = SQLAlchemy(app)
moment = Moment(app)
app.secret_key = "38ZNl5gHOntQqR_cN1QgEDmkPUGMSyE20FplDIQYancixFyxC0H-Yxvxm3NlH__ip-TsrHYxQoCmVE5x-TtlZw"
PIN_CODE = os.environ.get('PIN_CODE')


# --- Таблица Счета ---
class Checks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(40), nullable=False)
    summ = db.Column(db.Integer)


# --- Таблица Категории ---
class Categories(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    naming = db.Column(db.String(40), nullable=False)


# --- Таблица Операции ---
class Operations(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    summa = db.Column(db.Integer)
    comment = db.Column(db.String(100))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    check_id = db.Column(db.Integer)
    check_name = db.Column(db.String(40))
    categ_id = db.Column(db.String(40))


# --- Таблица Долги ---
class Debts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    summ = db.Column(db.Integer)
    debt = db.Column(db.String(40), nullable=False)


# --- Таблица Менеджеры ---
class Manager(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    percent = db.Column(db.Float)
    role = db.Column(db.String(20))
    goal = db.Column(db.Integer)
    department_id = db.Column(db.Integer)  # Привязка к отделу


# --- Таблица отгрузки ---
class Shipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.String(20))
    week = db.Column(db.Integer)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    deal_id = db.Column(db.Integer)
    manager = db.Column(db.String(100))
    supplier = db.Column(db.String(100))
    delivery_service = db.Column(db.String(100))
    address = db.Column(db.String(200))
    source = db.Column(db.String(100))
    client_phone = db.Column(db.String(20))
    is_class = db.Column(db.String(10))
    client_name = db.Column(db.String(100))
    product = db.Column(db.String(100))
    client_payment = db.Column(db.Float)
    supplier_payment = db.Column(db.Float)
    logistics = db.Column(db.Float)
    tax = db.Column(db.Float)
    forwarder_payment = db.Column(db.Float)
    other_expenses = db.Column(db.Float)
    delta = db.Column(db.Float)
    forwarder_name = db.Column(db.String(100))
    upd_logistic = db.Column(db.String(1000))
    upd_product = db.Column(db.String(1000))

    def calculate_delta(self):
        return (self.client_payment - self.supplier_payment -
                self.logistics - self.tax -
                self.forwarder_payment - self.other_expenses)


# --- Таблица изменение баланса менеджера ---
class ManagerBalance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    manager_id = db.Column(db.Integer, db.ForeignKey(
        'manager.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    comment = db.Column(db.String(100))
    payment_type = db.Column(db.String(50), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    shipment_id = db.Column(db.Integer, default=0)


# --- Таблица Сотрудники ---
class Persons(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    salary = db.Column(db.Float, default=0.0)


# --- Таблица изменение баланса сотрудника ---
class PersonsBalance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey(
        'manager.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    comment = db.Column(db.String(100))
    payment_type = db.Column(db.String(50), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)


# --- Таблица Отделы продаж ---
class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    # Цель отдела за неделю в рублях
    weekly_goal = db.Column(db.Float, nullable=False)
    rop_percent = db.Column(db.Float, default=0)


# --- Таблица Бонусные выплаты ---
class BonusPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    # Начало недели (понедельник)
    week_start = db.Column(db.Date, nullable=False)
    # Общая дельта отдела за неделю
    total_delta = db.Column(db.Float, nullable=False)
    is_paid = db.Column(db.Boolean, default=False)  # Флаг выплаты бонуса


# --- Таблица выплата менеджеру ---
class IsPaidManagerBonus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    manager_name = db.Column(db.String(100))
    start_week = db.Column(db.DateTime)
    isPaid = db.Column(db.Boolean, default=False)
    id_man_bonus = db.Column(db.Integer)


# --- Таблица выплата отделу ---
class IsPaidDepartmentBonus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer)
    start_week = db.Column(db.DateTime)
    isPaid = db.Column(db.Boolean, default=False)


# --- Функции -----------------------------------------------------------------------------------
def rub_to_kop(rub_str):
    """Конвертирует строку с рублями (1.23) в копейки (123)"""
    try:
        if ',' in rub_str:
            rub_str = rub_str.replace(',', '.')
        rub = float(rub_str)
        return int(round(rub * 100))
    except (ValueError, TypeError):
        return 0


def kop_to_rub(kop):
    """Конвертирует копейки в рубли с форматированием"""
    return f"{kop / 100:.2f}"


@app.template_filter('rub')
def rub_format(kop):
    """Фильтр для форматирования копеек в рубли"""
    return f"{kop / 100:.2f}"


@app.template_filter('format_number')
def format_number_filter(value):
    try:
        num = float(value)
        return f"{num:,.2f}".replace(",", " ").replace(".", ",")
    except (TypeError, ValueError):
        return value


def login_required(view_func):
    def wrapper(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return view_func(*args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper





# --- Логин -----------------------------------------------------------------------------------
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





# --- Главная -----------------------------------------------------------------------------------
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


@app.route('/download/')
@login_required
def download():
    opers = Operations.query.all()
    data = [{'№': oper.id, 'Сумма': oper.summa / 100.0, 'Комментарий': oper.comment, 'Дата': oper.date, 'Счет': oper.check_name, 'Категория': oper.categ_id}
            for oper in opers]
    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Операции')

    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='Операции.xlsx')





# --- Счета -----------------------------------------------------------------------------------
@app.route('/checks/<int:id>', methods=['POST', 'GET'])
@login_required
def checks_id(id):
    allcheck = Checks.query.get(id)
    allopp = Operations.query.order_by(Operations.date.desc()).all()
    allcateg = Categories.query.all()
    if request.method == 'POST':
        summa_kop = rub_to_kop(request.form['summ_op'])

        # Создаем операцию с суммой в копейках
        oper = Operations(
            summa=summa_kop,
            comment=request.form['comm_op'],
            check_id=id,
            check_name=allcheck.title,
            categ_id=request.form['categories']
        )

        # Обновляем сумму счета
        allcheck.summ += summa_kop
        try:
            db.session.add(oper)
            db.session.commit()
            return redirect(f'/checks/{id}')
        except:
            return render_template('Не удалось добавить транзакцию')
    else:
        return render_template('checks/check.html', allcheck=allcheck, allopp=allopp, allcateg=allcateg)


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





# --- Операции -----------------------------------------------------------------------------------
@app.route('/oper/<int:id>/', methods=['POST', 'GET'])
@login_required
def oper_id(id):
    allopp = Operations.query.get(id)
    checkelem = Checks.query.get(allopp.check_id)
    allcateg = Categories.query.all()

    if request.method == 'POST':
        new_summa_kop = rub_to_kop(request.form['summ_up'])

        # Обновляем суммы
        old_summa_kop = allopp.summa
        delta = new_summa_kop - old_summa_kop

        checkelem.summ += delta
        allopp.summa = new_summa_kop
        allopp.comment = request.form['comment_up']
        allopp.categ_id = request.form['categories']
        try:
            db.session.commit()
            return redirect(f'/oper/{id}')
        except:
            return render_template('Не удалось редактировать транзакцию')
    else:
        return render_template('checks/operation.html', allopp=allopp, checkelem=checkelem, allcateg=allcateg)


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





# --- Долги -----------------------------------------------------------------------------------
@app.route("/debts/", methods=['POST', 'GET'])
@login_required
def debts():
    alldebts = Debts.query.all()
    total_debt = sum(debt.summ for debt in alldebts)
    if request.method == 'POST':
        debt = request.form['debtname']
        summ = rub_to_kop(request.form['debtsumm'])
        errors = []
        if not debt:
            errors.append('Имя не может быть пустым')
        if errors:
            for error in errors:
                flash(error)
            return redirect(url_for('debts'))
        debtadd = Debts(summ=summ, debt=debt)
        try:
            db.session.add(debtadd)
            db.session.commit()
            return redirect('/debts')
        except:
            return 'При добавлении долга произошла ошибка!'
    else:
        return render_template('debt/debts.html', alldebts=alldebts, total_debt=total_debt)


@app.route('/debt/<int:id>', methods=['POST', 'GET'])
@login_required
def debt(id):
    alldebt = Debts.query.get(id)
    if request.method == 'POST':
        alldebt.debt = request.form['debtname']
        alldebt.summ = rub_to_kop(request.form['debtsumm'])
        try:
            db.session.commit()
            return redirect(f'/debt/{id}')
        except:
            return 'Не удалось редактировать долг'

    return render_template('debt/debt.html', alldebt=alldebt)


@app.route('/debt/<int:id>/del')
@login_required
def debt_delete(id):
    debt = Debts.query.get_or_404(id)
    try:
        db.session.delete(debt)
        db.session.commit()
        return redirect(f'/debts')
    except:
        return "При удалении долга произошла ошибка"





# --- Категории -----------------------------------------------------------------------------------
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
        return render_template('categ/categories.html', allcateg=allcateg)


@app.route('/categ/<int:id>', methods=['POST', 'GET'])
@login_required
def categ(id):
    allcateg = Categories.query.get(id)
    allopp = Operations.query.order_by(Operations.date.desc()).all()
    allcheck = Checks.query.all()
    last_name = allcateg.naming
    if request.method == 'POST':
        allcateg.naming = request.form['name']
        for i in allopp:
            if i.categ_id == last_name:
                i.categ_id = allcateg.naming
        try:
            db.session.commit()
            return redirect(f'/categ/{id}')
        except:
            return 'Не удалось редактировать категорию'

    return render_template('categ/categ.html', allcateg=allcateg, allopp=allopp, allcheck=allcheck)


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





# --- Вкладка металл -----------------------------------------------------------------------------------
@app.route('/metall/')
@login_required
def metall():
    return render_template('metall/metall.html')





# --- Отделы продаж -----------------------------------------------------------------------------------
@app.route('/departments', methods=['GET', 'POST'])
@login_required
def departments():
    if request.method == 'POST':
        name = request.form['name']
        weekly_goal = request.form['weekly_goal']
        rop_percent = float(request.form['rop_percent']) / 100

        new_department = Department(name=name, weekly_goal=weekly_goal, rop_percent=rop_percent)

        db.session.add(new_department)
        db.session.commit()
        return redirect('/departments')

    departments = Department.query.all()
    return render_template('metall/departments/departments.html', departments=departments)


@app.route('/departments/<int:id>', methods=['GET', 'POST'])
@login_required
def department_detail(id):
    department = Department.query.get(id)
    departments = Department.query.all()

    if request.method == 'POST':
        name = request.form['name']
        percent = float(request.form['percent']) / 100
        role = request.form['role']
        goal = request.form['goal']
        department_id = id

        if Manager.query.filter_by(name=name).first():
            flash('Менеджер с таким именем уже существует!', 'danger')
        else:
            new_manager = Manager(
                name=name,
                percent=percent,
                role=role,
                goal=goal,
                department_id=department_id
            )
            db.session.add(new_manager)
            db.session.commit()
        return redirect(f'/departments/{id}')

    managers = Manager.query.filter_by(department_id=id).all()



    return render_template('metall/departments/department_detail.html', department=department, managers=managers, departments=departments)


@app.route('/departments/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_department(id):
    department = Department.query.get(id)
    if request.method == 'POST':
        department.name = request.form['name']
        department.weekly_goal = request.form['weekly_goal']
        department.rop_percent = float(request.form['rop_percent']) / 100

        db.session.commit()
        return redirect(url_for('department_detail', id=department.id))
    
    return render_template(
        'metall/departments/edit_department.html',
        department=department
    )



@app.route('/departments/<int:id>/delete', methods=['POST'])
def department_delete(id):
    department = Department.query.get_or_404(id)
    Manager.query.filter_by(department_id=id).update({'department_id': None})

    db.session.delete(department)
    db.session.commit()

    return redirect(url_for('departments'))





# --- Менеджеры -----------------------------------------------------------------------------------
@app.route('/managers/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_manager(id):
    manager = Manager.query.get_or_404(id)
    shipment = Shipment.query.filter_by(manager=manager.name).all()
    departments = Department.query.all()

    if request.method == 'POST':
        manager.name = request.form['name']
        manager.percent = float(request.form['percent']) / 100
        manager.role = request.form['role']
        manager.goal = request.form['goal']
        manager.department_id = request.form['department_id']
        for ship in shipment:
            ship.manager = manager.name

        db.session.commit()
        return redirect(url_for('manager_detail', id=manager.id))

    # Переводим проценты в % для отображения в форме
    percent_display = manager.percent * 100
    return render_template(
        'metall/managers/edit_manager.html',
        manager=manager,
        percent_display=percent_display,
        departments=departments
    )


@app.route('/managers/<int:id>')
@login_required
def manager_detail(id):
    manager = Manager.query.get_or_404(id)
    allchecks = Checks.query.all()
    department = Department.query.filter_by(id=manager.department_id).first()

    # Фильтрация операций
    period = request.args.get('period', 'all')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Инициализация переменных дат
    today = datetime.utcnow().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    start_of_month = today.replace(day=1)
    end_of_month = (start_of_month + timedelta(days=32)
                    ).replace(day=1) - timedelta(days=1)

    # Фильтрация операций (существующий код)
    balance_query = ManagerBalance.query.filter_by(manager_id=id)
    filtered_query = balance_query

    if period == 'week':
        filtered_query = filtered_query.filter(
            ManagerBalance.date >= start_of_week,
            ManagerBalance.date <= end_of_week
        )
    elif period == 'month':
        filtered_query = filtered_query.filter(
            ManagerBalance.date >= start_of_month,
            ManagerBalance.date <= end_of_month
        )
    elif period == 'custom' and start_date and end_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            filtered_query = filtered_query.filter(
                ManagerBalance.date >= start,
                ManagerBalance.date <= end
            )
        except ValueError:
            pass

    period_balance = filtered_query.with_entities(
        func.sum(ManagerBalance.amount)).scalar() or 0.0
    
    allManageBalance = filtered_query.order_by(
        ManagerBalance.date.desc()).all()

    balance = balance_query.with_entities(
        func.sum(ManagerBalance.amount)).scalar() or 0.0

    # Фильтрация ОТГРУЗОК (новый код)
    shipments_query = Shipment.query.filter_by(manager=manager.name)

    if period == 'week':
        shipments_query = shipments_query.filter(
            Shipment.date >= start_of_week,
            Shipment.date <= end_of_week
        )
    elif period == 'month':
        shipments_query = shipments_query.filter(
            Shipment.date >= start_of_month,
            Shipment.date <= end_of_month
        )
    elif period == 'custom' and start_date and end_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            shipments_query = shipments_query.filter(
                Shipment.date >= start,
                Shipment.date <= end
            )
        except ValueError:
            pass

    # Вычисляем сумму отгрузок за период
    period_shipments_sum = shipments_query.with_entities(
        func.sum(Shipment.delta)).scalar() or 0.0
    shipments = shipments_query.order_by(Shipment.date.desc()).all()

    return render_template(
        'metall/managers/manager_detail.html',
        manager=manager,
        shipments=shipments,
        allchecks=allchecks,
        allManageBalance=allManageBalance,
        current_period=period,
        start_date=start_date,
        end_date=end_date,
        period_balance=period_balance,
        period_shipments_sum=period_shipments_sum,
        department=department,
        balance = balance
        # Новая переменная
    )


@app.route('/managers/<int:id>/delete', methods=['POST'])
@login_required
def delete_manager(id):
    manager = Manager.query.get_or_404(id)

    # Удаляем все связанные записи баланса
    ManagerBalance.query.filter_by(manager_id=id).delete()

    db.session.delete(manager)
    db.session.commit()
    # Предполагается, что есть роут для списка менеджеров
    return redirect(url_for('manager_detail', id=manager.id))


# --- Изменения баланса менеджера ---
@app.route('/managers/<int:manager_id>/pay>', methods=['POST'])
@login_required
def pay_manager(manager_id):
    manager = Manager.query.get_or_404(manager_id)

    amount = float(request.form['amount'])
    payment_type = request.form['payment_type']
    check_id = int(request.form['check_id'])

    # Получаем счет
    check = Checks.query.get_or_404(check_id)

    amount_kop = rub_to_kop(str(amount))

    addbalance = ManagerBalance(
        manager_id=manager.id,
        amount=amount,
        comment=f"{manager.name} {payment_type}",
        payment_type=payment_type,
    )
    db.session.add(addbalance)

    # Создаем операцию
    operation = Operations(
        summa=+amount_kop,
        comment=f"{manager.name} {payment_type}",
        date=datetime.utcnow(),
        check_id=check.id,
        check_name=check.title,
        categ_id='ФОТ'
    )

    db.session.add(operation)

    # Обновляем баланс счета
    check.summ += amount_kop

    db.session.commit()
    return redirect(url_for('manager_detail', id=manager.id))


@app.route('/managers/<int:manager_add_id>/add>', methods=['POST'])
@login_required
def add_manager(manager_add_id):
    manager = Manager.query.get_or_404(manager_add_id)

    add_amount = float(request.form['add_amount'])
    add_comment = request.form['add_comment']
    add_type = request.form['add_type']

    # Создаем запись о выплате
    addbalance = ManagerBalance(
        manager_id=manager.id,
        amount=add_amount,
        comment=add_comment,
        payment_type=add_type,
    )
    db.session.add(addbalance)

    db.session.commit()
    return redirect(url_for('manager_detail', id=manager.id))


@app.route('/managers/<int:manager_fine_id>/fine>', methods=['POST'])
@login_required
def fine_manager(manager_fine_id):
    manager = Manager.query.get_or_404(manager_fine_id)

    fine_summ = float(request.form['fine_summ'])
    fine_comment = request.form['fine_comment']

    # Создаем запись о выплате
    addbalance = ManagerBalance(
        manager_id=manager.id,
        amount=fine_summ,
        comment=fine_comment,
        payment_type='Штраф',
    )
    db.session.add(addbalance)

    db.session.commit()
    return redirect(url_for('manager_detail', id=manager.id))


@app.route('/op_detail/<int:id>', methods=['GET', 'POST'])
@login_required
def op_detail(id):
    ManBalance = ManagerBalance.query.get(id)

    if request.method == 'POST':
        ManBalance.amount = request.form['summ_mb']
        ManBalance.comment = request.form['comment_mb']
        db.session.commit()
        return redirect(url_for('op_detail', id=id))

    return render_template(
        'metall/managers/op_detail.html',
        ManBalance=ManBalance
    )


@app.route('/op_detail/<int:id>/del')
@login_required
def op_delete(id):
    ManBalance = ManagerBalance.query.get_or_404(id)
    manager = Manager.query.get(ManBalance.manager_id)
    try:
        db.session.delete(ManBalance)
        db.session.commit()
        return redirect(url_for('manager_detail', id=manager.id))
    except:
        return "При удалении операции произошла ошибка"


@app.route('/managers/<int:id>/export_operations', methods=['GET'])
@login_required
def export_manager_operations(id):
    manager = Manager.query.get_or_404(id)

    # Применяем те же фильтры, что и в manager_detail
    period = request.args.get('period', 'all')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    balance_query = ManagerBalance.query.filter_by(manager_id=id)
    filtered_query = balance_query

    today = datetime.utcnow().date()
    if period == 'week':
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        filtered_query = filtered_query.filter(
            ManagerBalance.date >= start_of_week,
            ManagerBalance.date <= end_of_week
        )
    elif period == 'month':
        start_of_month = today.replace(day=1)
        end_of_month = (start_of_month + timedelta(days=32)
                        ).replace(day=1) - timedelta(days=1)
        filtered_query = filtered_query.filter(
            ManagerBalance.date >= start_of_month,
            ManagerBalance.date <= end_of_month
        )
    elif period == 'custom' and start_date and end_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            filtered_query = filtered_query.filter(
                ManagerBalance.date >= start,
                ManagerBalance.date <= end
            )
        except ValueError:
            pass

    operations = filtered_query.order_by(ManagerBalance.date.desc()).all()

    # Создаем DataFrame
    data = [{
        'Дата': op.date.strftime('%Y-%m-%d %H:%M'),
        'Сумма': op.amount,
        'Тип операции': op.payment_type,
        'Комментарий': op.comment
    } for op in operations]

    df = pd.DataFrame(data)

    # Создаем Excel файл в памяти
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Операции')

    output.seek(0)

    # Формируем имя файла
    filename = f"Операции_{manager.name}_{datetime.now().strftime('%Y-%m-%d')}.xlsx"

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )





# --- Сотрудники -----------------------------------------------------------------------------------
@app.route('/persons', methods=['GET', 'POST'])
@login_required
def persons():
    if request.method == 'POST':
        name = request.form['name_persons']

        if Persons.query.filter_by(name=name).first():
            flash('Менеджер с таким именем уже существует!', 'danger')
        else:
            new_persons = Persons(
                name=name,
            )
            db.session.add(new_persons)
            db.session.commit()

        return redirect(url_for('persons'))

    persons_list = Persons.query.all()
    return render_template('metall/persons/persons.html', persons=persons_list)


@app.route('/persons/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_person(id):
    person = Persons.query.get_or_404(id)

    if request.method == 'POST':
        person.name = request.form['name']

        db.session.commit()
        return redirect(url_for('persons'))

    # Переводим проценты в % для отображения в форме
    return render_template(
        'metall/persons/edit_person.html',
        person=person,
    )


@app.route('/persons/<int:id>')
@login_required
def person_detail(id):
    person = Persons.query.get_or_404(id)
    allchecks = Checks.query.all()

    # Фильтрация операций
    period = request.args.get('period', 'all')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Базовый запрос
    balance_query = PersonsBalance.query.filter_by(person_id=id)

    # Сохраняем запрос с фильтрами для вычисления суммы
    filtered_query = balance_query

    # Применение фильтров
    if period == 'week':
        today = datetime.utcnow().date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=7)
        filtered_query = filtered_query.filter(
            PersonsBalance.date >= start_of_week,
            PersonsBalance.date <= end_of_week
        )
    elif period == 'month':
        today = datetime.utcnow().date()
        start_of_month = today.replace(day=1)
        end_of_month = (start_of_month + timedelta(days=32)
                        ).replace(day=1) - timedelta(days=1)
        filtered_query = filtered_query.filter(
            PersonsBalance.date >= start_of_month,
            PersonsBalance.date <= end_of_month
        )
    elif period == 'custom' and start_date and end_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            filtered_query = filtered_query.filter(
                PersonsBalance.date >= start,
                PersonsBalance.date <= end
            )
        except ValueError:
            pass

    # Вычисляем сумму операций за период
    period_balance = filtered_query.with_entities(
        func.sum(PersonsBalance.amount)).scalar() or 0.0

    allPersonBalance = filtered_query.order_by(
        PersonsBalance.date.desc()).all()

    return render_template(
        'metall/persons/person_detail.html',
        person=person,
        allchecks=allchecks,
        allPersonBalance=allPersonBalance,
        current_period=period,
        start_date=start_date,
        end_date=end_date,
        period_balance=period_balance  # Передаем баланс периода
    )


@app.route('/persons/<int:id>/delete', methods=['POST'])
@login_required
def delete_person(id):
    person = Persons.query.get_or_404(id)

    # Удаляем все связанные записи баланса
    PersonsBalance.query.filter_by(person_id=id).delete()

    db.session.delete(person)
    db.session.commit()
    # Предполагается, что есть роут для списка менеджеров
    return redirect(url_for('persons'))


# --- Изменения баланса сотрудника ---
@app.route('/persons/<int:person_id>/pay>', methods=['POST'])
@login_required
def pay_person(person_id):
    person = Persons.query.get_or_404(person_id)

    amount = float(request.form['amount'])
    payment_type = request.form['payment_type']
    check_id = int(request.form['check_id'])

    # Получаем счет
    check = Checks.query.get_or_404(check_id)

    amount_kop = rub_to_kop(str(amount))

    addbalance = PersonsBalance(
        person_id=person.id,
        amount=amount,
        comment=f"{person.name} {payment_type}",
        payment_type=payment_type,
    )
    db.session.add(addbalance)

    # Создаем операцию
    operation = Operations(
        summa=+amount_kop,
        comment=f"{person.name} {payment_type}",
        date=datetime.utcnow(),
        check_id=check.id,
        check_name=check.title,
        categ_id='ФОТ'
    )

    db.session.add(operation)

    # Обновляем баланс счета
    check.summ += amount_kop

    # Обновляем баланс менеджера
    person.salary += amount

    db.session.commit()
    return redirect(url_for('persons'))


@app.route('/persons/<int:person_add_id>/add>', methods=['POST'])
@login_required
def add_person(person_add_id):
    person = Persons.query.get_or_404(person_add_id)

    add_amount = float(request.form['add_amount'])
    add_comment = request.form['add_comment']
    add_type = request.form['add_type']

    # Создаем запись о выплате
    addbalance = PersonsBalance(
        person_id=person.id,
        amount=add_amount,
        comment=add_comment,
        payment_type=add_type,
    )
    db.session.add(addbalance)

    person.salary += add_amount

    db.session.commit()
    return redirect(url_for('persons'))


@app.route('/persons/<int:person_fine_id>/fine>', methods=['POST'])
@login_required
def fine_person(person_fine_id):
    person = Persons.query.get_or_404(person_fine_id)

    fine_summ = float(request.form['fine_summ'])
    fine_comment = request.form['fine_comment']

    # Создаем запись о выплате
    addbalance = PersonsBalance(
        person_id=person.id,
        amount=fine_summ,
        comment=fine_comment,
        payment_type='Штраф',
    )
    db.session.add(addbalance)

    person.salary += fine_summ

    db.session.commit()
    return redirect(url_for('persons'))


@app.route('/op_person/<int:id>', methods=['GET', 'POST'])
@login_required
def op_person(id):
    PerBalance = PersonsBalance.query.get(id)
    person = Persons.query.get(PerBalance.person_id)

    old_amount = PerBalance.amount

    if request.method == 'POST':
        PerBalance.amount = request.form['summ_pb']
        PerBalance.comment = request.form['comment_pb']
        new_amount = PerBalance.amount
        person.salary -= float(old_amount)
        person.salary += float(new_amount)
        db.session.commit()
        return redirect(url_for('op_person', id=id))

    return render_template(
        'metall/persons/op_person.html',
        PerBalance=PerBalance
    )


@app.route('/op_person/<int:id>/del')
@login_required
def op_person_delete(id):
    PerBalance = PersonsBalance.query.get_or_404(id)
    person = Persons.query.get(PerBalance.person_id)
    try:
        db.session.delete(PerBalance)
        person.salary -= PerBalance.amount
        db.session.commit()
        return redirect(f'/persons/{person.id}')
    except:
        return "При удалении операции произошла ошибка"





# --- Отгрузки -----------------------------------------------------------------------------------
@app.route('/shipments', methods=['GET'])
@login_required
def shipments():
    # Фильтрация
    manager_filter = request.args.get('manager')
    period_filter = request.args.get('period', 'all')  # all/month/week/custom
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = Shipment.query

    if manager_filter:
        query = query.filter_by(manager=manager_filter)

    # Фильтрация по периоду
    today = datetime.today().date()
    if period_filter == 'month':
        first_day = today.replace(day=1)
        last_day = (first_day + timedelta(days=32)
                    ).replace(day=1) - timedelta(days=1)
        query = query.filter(Shipment.date.between(first_day, last_day))
    elif period_filter == 'week':
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=7)
        query = query.filter(Shipment.date.between(monday, sunday))
    elif period_filter == 'custom' and start_date and end_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Shipment.date.between(start, end))
        except ValueError:
            pass  # Обработка неверного формата даты

    shipments_list = query.order_by(Shipment.date.desc()).all()
    managers = [m.name for m in Manager.query.all()]

    return render_template('metall/shipments/shipments.html',
                           shipments=shipments_list,
                           managers=managers,
                           current_manager=manager_filter,
                           period=period_filter,
                           start_date=start_date,
                           end_date=end_date)


@app.route('/shipments/<int:id>')
@login_required
def shipment_detail(id):
    shipment = Shipment.query.get_or_404(id)
    return render_template('metall/shipments/shipment_detail.html', shipment=shipment)


@app.route('/add_shipment', methods=['GET', 'POST'])
@login_required
def add_shipment():
    managers = [m.name for m in Manager.query.all()]

    if request.method == 'POST':
        # Создаем объект отгрузки
        new_shipment = Shipment(
            month=request.form['month'],
            week=int(request.form['week']),
            date=datetime.strptime(request.form['date'], '%Y-%m-%d'),
            deal_id=int(request.form['deal_id']),
            manager=request.form['manager'],
            supplier=request.form['supplier'],
            delivery_service=request.form['delivery_service'],
            address=request.form['address'],
            source=request.form['source'],
            client_phone=request.form['client_phone'],
            is_class=request.form['is_class'],
            client_name=request.form['client_name'],
            product=request.form['product'],
            client_payment=float(request.form['client_payment']),
            supplier_payment=float(request.form['supplier_payment']),
            logistics=float(request.form['logistics']),
            tax=float(request.form['tax']),
            forwarder_payment=float(request.form['forwarder_payment']),
            other_expenses=float(request.form['other_expenses']),
            forwarder_name=request.form['forwarder_name'],
            upd_logistic=request.form['upd_logistic'],
            upd_product=request.form['upd_product']
        )





        # Рассчитываем дельту
        new_shipment.delta = new_shipment.calculate_delta()

        db.session.add(new_shipment)
        db.session.flush()





        # Начисление менеджеру
        manager = Manager.query.filter_by(name=new_shipment.manager).first()
        amount_to_add = new_shipment.delta * manager.percent

        addbalance = ManagerBalance(
            manager_id=manager.id,
            amount=amount_to_add,
            comment=f"Отгрузка. ID: {new_shipment.deal_id}",
            payment_type='Отгрузка',
            date=new_shipment.date,
            shipment_id=new_shipment.id
        )

        forward = Manager.query.filter_by(name=new_shipment.forwarder_name).first()

        if forward:
            addforward = ManagerBalance(
                manager_id=forward.id,
                amount=new_shipment.forwarder_payment,
                comment=f"Экспедиторские, отгрузка:. ID: {new_shipment.deal_id}",
                payment_type='Экспедиторские',
                date=new_shipment.date,
                shipment_id=new_shipment.id
            )
            db.session.add(addforward)





        db.session.add(addbalance)
        db.session.flush()

        rop = Manager.query.filter_by(role='РОП', department_id=manager.department_id).first()
        department = Department.query.filter_by(id=manager.department_id).first()
        if department.rop_percent > 0:
            if rop:
                if manager.role == 'Менеджер':
                    addbalancerop = ManagerBalance(
                        manager_id = rop.id,
                        amount = new_shipment.delta*department.rop_percent,
                        comment = f"Отгрузка. ID: {new_shipment.deal_id}",
                        payment_type=f'Отгрузка менеджер {manager.name}',
                        date=new_shipment.date,
                        shipment_id=new_shipment.id
                    )
                    db.session.add(addbalancerop)


        #если выполнена цель менеджера, то выплачиваем менеджеру
        start_of_week = new_shipment.date - \
            timedelta(days=new_shipment.date.weekday())
        end_of_week = start_of_week + timedelta(days=7)
        shipments_query = Shipment.query.filter_by(manager=manager.name)
        shipments_query = shipments_query.filter(
            Shipment.date >= start_of_week,
            Shipment.date <= end_of_week
        )

        period_shipments_sum = shipments_query.with_entities(
            func.sum(Shipment.delta)).scalar() or 0.0

        if period_shipments_sum >= manager.goal:
            isPaidManager = IsPaidManagerBonus.query.filter_by(manager_name=manager.name,
                                                               start_week=start_of_week).first()
            if isPaidManager and isPaidManager.isPaid:
                bonus = ManagerBalance.query.get(isPaidManager.id_man_bonus)
                bonus.amount = (period_shipments_sum*0.05)
                if department.rop_percent > 0:
                    RBalance = ManagerBalance.query.filter_by(shipment_id=new_shipment.id, payment_type=f'Отгрузка менеджер {manager.name}').first()
                    if RBalance:
                        RBalance.amount = period_shipments_sum*0.015
            else:
                addbonusbalance = ManagerBalance(
                    manager_id=manager.id,
                    amount=period_shipments_sum*0.05,
                    comment=f"Бонус за закрытую личную цель. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}",
                    payment_type='Бонус',
                    date=new_shipment.date
                )
                db.session.add(addbonusbalance)
                db.session.commit()

                isPaid = IsPaidManagerBonus(
                    manager_name=manager.name,
                    start_week=start_of_week,
                    isPaid=True,
                    id_man_bonus=addbonusbalance.id
                )
                db.session.add(isPaid)

                if department.rop_percent > 0:
                    if rop:
                        if manager.role == 'Менеджер':
                            addbalancerop = ManagerBalance(
                                manager_id = rop.id,
                                amount = period_shipments_sum*0.015,
                                comment = f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}",
                                payment_type=f'Премия отгрузка менеджер {manager.name}',
                                date=new_shipment.date,
                                shipment_id=new_shipment.id
                            )
                            db.session.add(addbalancerop)
        else:
            isPaid = IsPaidManagerBonus.query.filter_by(
                manager_name=manager.name, start_week=start_of_week).first()
            if isPaid and isPaid.isPaid:
                del_bonus = ManagerBalance.query.get_or_404(
                    isPaid.id_man_bonus)
                del_paid = IsPaidManagerBonus.query.get_or_404(isPaid.id)
                db.session.delete(del_bonus)
                db.session.delete(del_paid)
            if department.rop_percent > 0:
                RBalance = ManagerBalance.query.filter_by(comment = f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}", payment_type=f'Премия отгрузка менеджер {manager.name}').first()
                if RBalance:
                    db.session.delete(RBalance)





        #если выполнена цель отдела, то выплачиваем менеджеру
        dep_managers = Manager.query.filter_by(department_id = department.id).all()
        total_delta = 0
        manager_deltas = {}

        for manager in dep_managers:
        # Считаем дельту менеджера за неделю
            shipments = Shipment.query.filter(
                Shipment.manager == manager.name,
                Shipment.date >= start_of_week,
                Shipment.date <= end_of_week
            ).all()
        
            manager_delta = sum(ship.delta for ship in shipments)
            manager_deltas[manager.id] = manager_delta
            total_delta += manager_delta
        
        if total_delta >= department.weekly_goal:
            isPaidDep = IsPaidDepartmentBonus.query.filter_by(department_id=department.id, start_week = start_of_week).first()
            if isPaidDep and isPaidDep.isPaid:
                for manager_id, delta in manager_deltas.items():
                    id_dep_bonus = ManagerBalance.query.filter_by(manager_id=manager_id, comment=f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}").first()
                    id_dep_bonus.amount = delta*(0.05)
                    db.session.flush()
            else:
                for manager_id, delta in manager_deltas.items():
                    balance_entry = ManagerBalance(
                        manager_id=manager_id,
                        amount=delta * 0.05,
                        comment=f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}",
                        payment_type='Бонус',
                        date=new_shipment.date
                    )
                    db.session.add(balance_entry)

                DepPaid = IsPaidDepartmentBonus(
                    department_id = department.id,
                    start_week = start_of_week,
                    isPaid=True
                )
                db.session.add(DepPaid)
        else:
            isPaidDep = IsPaidDepartmentBonus.query.filter_by(department_id=department.id, start_week = start_of_week).first()
            if isPaidDep and isPaidDep.isPaid:
                for manager_id, delta in manager_deltas.items():
                    all_dep_bonus = ManagerBalance.query.filter_by(manager_id=manager_id, comment=f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}").first()
                    del_dep_bonus = ManagerBalance.query.get_or_404(all_dep_bonus.id)
                    db.session.delete(del_dep_bonus) 
                    print(del_dep_bonus)
                del_dep_paid = IsPaidDepartmentBonus.query.get_or_404(isPaidDep.id)
                db.session.delete(del_dep_paid)





        db.session.commit()
        return redirect(url_for('shipments'))

    return render_template('metall/shipments/add_shipment.html', managers=managers)


@app.route('/shipments/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_shipment(id):
    shipment = Shipment.query.get_or_404(id)
    managers = [m.name for m in Manager.query.all()]

    old_manager = Manager.query.filter_by(name=shipment.manager).first()
    rop = Manager.query.filter_by(role='РОП', department_id=old_manager.department_id).first()
    department = Department.query.filter_by(id=old_manager.department_id).first()
    
    if request.method == 'POST':
        # Сохраняем нового менеджера и дату из формы ДО обновления объекта
        new_manager_name = request.form['manager']
        new_date = datetime.strptime(request.form['date'], '%Y-%m-%d')\
        
        old_date = shipment.date
        
        #удаляем старую выплату менеджера
        if old_manager:
            start_of_week = old_date - timedelta(days=old_date.weekday())
            end_of_week = start_of_week + timedelta(days=7)

            shipments_query = Shipment.query.filter_by(manager=old_manager.name)
            shipments_query = shipments_query.filter(
                Shipment.date >= start_of_week,
                Shipment.date <= end_of_week
            )
            period_shipments_sum = shipments_query.with_entities(
                func.sum(Shipment.delta)).scalar() or 0.0

            period_shipments_sum -= shipment.delta

            if period_shipments_sum >= old_manager.goal:
                isPaid = IsPaidManagerBonus.query.filter_by(
                    manager_name=old_manager.name, start_week=start_of_week).first()
                if isPaid and isPaid.isPaid:
                    bonus = ManagerBalance.query.get(isPaid.id_man_bonus)
                    bonus.amount = (period_shipments_sum*0.05)
                    if department.rop_percent > 0:
                        RBalance = ManagerBalance.query.filter_by(shipment_id=shipment.id, payment_type=f'Отгрузка менеджер {old_manager.name}').first()
                        if RBalance:
                            RBalance.amount = period_shipments_sum*0.015
                else:
                    addBonusBalance = ManagerBalance(
                        manager_id=old_manager .id,
                        amount=period_shipments_sum*0.05,
                        comment=f"Бонус за закрытую личную цель. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}",
                        payment_type='Бонус',
                        date=old_date
                    )
                    db.session.add(addBonusBalance)
                    db.session.flush()

                    isPaidBonus = IsPaidManagerBonus(
                        manager_name=old_manager.name,
                        start_week=start_of_week,
                        isPaid=True,
                        id_man_bonus=addBonusBalance.id
                    )
                    db.session.add(isPaidBonus)
                    if department.rop_percent > 0:
                        if rop:
                            if old_manager.role == 'Менеджер':
                                addbalancerop = ManagerBalance(
                                    manager_id = rop.id,
                                    amount = period_shipments_sum*0.015,
                                    comment = f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}",
                                    payment_type=f'Премия отгрузка менеджер {old_manager.name}',
                                    date=shipment.date,
                                    shipment_id=shipment.id
                                )
                                db.session.add(addbalancerop)

            else:
                isPaid = IsPaidManagerBonus.query.filter_by(
                    manager_name=old_manager.name, start_week=start_of_week).first()
                if isPaid and isPaid.isPaid:
                    del_new_bonus = ManagerBalance.query.get_or_404(
                        isPaid.id_man_bonus)
                    del_new_paid = IsPaidManagerBonus.query.get_or_404(isPaid.id)
                    db.session.delete(del_new_bonus)
                    db.session.delete(del_new_paid)
                if department.rop_percent > 0:
                    RBalance = ManagerBalance.query.filter_by(comment = f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}", payment_type=f'Премия отгрузка менеджер {old_manager.name}').first()
                    if RBalance:
                        db.session.delete(RBalance)
   

        #Удаляем старую выплату отдела

        if department:
            dep_managers = Manager.query.filter_by(department_id = department.id).all()
            
        total_delta = 0
        manager_deltas = {}

        if department:
            for manager in dep_managers:
            # Считаем дельту менеджера за неделю
                shipments = Shipment.query.filter(
                    Shipment.manager == manager.name,
                    Shipment.date >= start_of_week,
                    Shipment.date <= end_of_week
                ).all()
            
                manager_delta = sum(ship.delta for ship in shipments)
                manager_deltas[manager.id] = manager_delta
                total_delta += manager_delta

            total_delta -= shipment.delta

            if total_delta >= department.weekly_goal:
                isPaidDep = IsPaidDepartmentBonus.query.filter_by(department_id=department.id, start_week = start_of_week).first()
                if isPaidDep and isPaidDep.isPaid:
                    for manager_id, delta in manager_deltas.items():
                        id_dep_bonus = ManagerBalance.query.filter_by(manager_id=manager_id, comment=f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}").first()
                        id_dep_bonus.amount = delta*(0.05)
                        db.session.flush()
                else:
                    for manager_id, delta in manager_deltas.items():
                        balance_entry = ManagerBalance(
                            manager_id=manager_id,
                            amount=delta * 0.05,
                            comment=f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}",
                            payment_type='Бонус',
                            date=old_date
                        )
                        db.session.add(balance_entry)

                    DepPaid = IsPaidDepartmentBonus(
                        department_id = department.id,
                        start_week = start_of_week,
                        isPaid=True
                    )
                    db.session.add(DepPaid)
            else:
                isPaidDep = IsPaidDepartmentBonus.query.filter_by(department_id=department.id, start_week = start_of_week).first()
                if isPaidDep and isPaidDep.isPaid:
                    for manager_id, delta in manager_deltas.items():
                        all_dep_bonus = ManagerBalance.query.filter_by(manager_id=manager_id, comment=f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}").first()
                        del_dep_bonus = ManagerBalance.query.get_or_404(all_dep_bonus.id)
                        db.session.delete(del_dep_bonus) 
                        print(del_dep_bonus)
                    del_dep_paid = IsPaidDepartmentBonus.query.get_or_404(isPaidDep.id)
                    db.session.delete(del_dep_paid)



        forward = Manager.query.filter_by(name=shipment.forwarder_name).first()

        if forward:
            forwardPay = ManagerBalance.query.filter_by(manager_id=forward.id, payment_type='Экспедиторские', shipment_id=shipment.id).first()
            if forwardPay:
                delPay = ManagerBalance.query.get_or_404(forwardPay.id)
                db.session.delete(delPay)


        db.session.commit()




        # Обновляем данные отгрузки
        shipment.month = request.form['month']
        shipment.week = int(request.form['week'])
        shipment.date = new_date
        shipment.deal_id = int(request.form['deal_id'])
        shipment.manager = new_manager_name
        shipment.supplier = request.form['supplier']
        shipment.delivery_service = request.form['delivery_service']
        shipment.address = request.form['address']
        shipment.source = request.form['source']
        shipment.client_phone = request.form['client_phone']
        shipment.is_class = request.form['is_class']
        shipment.client_name = request.form['client_name']
        shipment.product = request.form['product']
        shipment.client_payment = float(request.form['client_payment'])
        shipment.supplier_payment = float(request.form['supplier_payment'])
        shipment.logistics = float(request.form['logistics'])
        shipment.tax = float(request.form['tax'])
        shipment.forwarder_payment = float(request.form['forwarder_payment'])
        shipment.other_expenses = float(request.form['other_expenses'])
        shipment.forwarder_name = request.form['forwarder_name']
        shipment.delta = shipment.calculate_delta()

        newMBalance = ManagerBalance.query.filter_by(shipment_id=id, payment_type='Отгрузка').first()
        manager = Manager.query.filter_by(name=shipment.manager).first()

        if old_manager:
            newMBalance.manager_id = manager.id
            newMBalance.amount = shipment.delta * manager.percent
            newMBalance.date = shipment.date
            newMBalance.comment = f"Отгрузка. ID: {shipment.deal_id}"

        else:
            amount_to_add = shipment.delta * manager.percent
            addbalance = ManagerBalance(
                manager_id=manager.id,
                amount=amount_to_add,
                comment=f"Отгрузка. ID: {shipment.deal_id}",
                payment_type='Отгрузка',
                date=shipment.date,
                shipment_id=shipment.id
            )
            db.session.add(addbalance)


        new_forward = Manager.query.filter_by(name=shipment.forwarder_name).first()
        if new_forward:
            addforward = ManagerBalance(
                manager_id=new_forward.id,
                amount=shipment.forwarder_payment,
                comment=f"Экспедиторские, отгрузка:. ID: {shipment.deal_id}",
                payment_type='Экспедиторские',
                date=shipment.date,
                shipment_id=shipment.id
            )
        
            db.session.add(addforward)
    



        rop = Manager.query.filter_by(role='РОП', department_id=manager.department_id).first()
        department = Department.query.filter_by(id=manager.department_id).first()
        newRBalance = ManagerBalance.query.filter_by(shipment_id=id, payment_type=f'Отгрузка менеджер {old_manager.name}').first()
        if department.rop_percent > 0:
            if old_manager:
                if rop:
                    if manager.role == 'Менеджер':
                        newRBalance.manager_id = rop.id
                        newRBalance.amount = shipment.delta * department.rop_percent
                        newRBalance.date = shipment.date
                        newRBalance.comment = f"Отгрузка. ID: {shipment.deal_id}"
            else:
                addbalancerop = ManagerBalance(
                    manager_id = rop.id,
                    amount = shipment.delta*department.rop_percent,
                    comment = f"Отгрузка. ID: {shipment.deal_id}",
                    payment_type=f'Отгрузка менеджер {manager.name}',
                    date=shipment.date,
                    shipment_id=shipment.id
                )
                db.session.add(addbalancerop)
        
        db.session.flush()
        




        #здесь создаем новую выплату
        start_of_week = shipment.date - \
            timedelta(days=shipment.date.weekday())
        end_of_week = start_of_week + timedelta(days=7)

        shipments_query = Shipment.query.filter_by(manager=manager.name)
        shipments_query = shipments_query.filter(
            Shipment.date >= start_of_week,
            Shipment.date <= end_of_week
        )

        period_shipments_sum = shipments_query.with_entities(
            func.sum(Shipment.delta)).scalar() or 0.0

        if period_shipments_sum >= manager.goal:
            isPaidManager = IsPaidManagerBonus.query.filter_by(manager_name=manager.name,
                                                               start_week=start_of_week).first()
            if isPaidManager and isPaidManager.isPaid:
                bonus = ManagerBalance.query.get(isPaidManager.id_man_bonus)
                bonus.amount = (period_shipments_sum*0.05)
                if department.rop_percent > 0:
                    RBalance = ManagerBalance.query.filter_by(shipment_id=shipment.id, payment_type=f'Отгрузка менеджер {manager.name}').first()
                    if RBalance:
                        RBalance.amount = period_shipments_sum*0.015
            else:
                addbonusbalance = ManagerBalance(
                    manager_id=manager.id,
                    amount=period_shipments_sum*0.05,
                    comment=f"Бонус за закрытую личную цель. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}",
                    payment_type='Бонус',
                    date=shipment.date
                )
                db.session.add(addbonusbalance)
                db.session.commit()

                isPaid = IsPaidManagerBonus(
                    manager_name=manager.name,
                    start_week=start_of_week,
                    isPaid=True,
                    id_man_bonus=addbonusbalance.id
                )
                db.session.add(isPaid)
                if department.rop_percent > 0:
                    if rop:
                        if manager.role == 'Менеджер':
                            addbalancerop = ManagerBalance(
                                manager_id = rop.id,
                                amount = period_shipments_sum*0.015,
                                comment = f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}",
                                payment_type=f'Премия отгрузка менеджер {manager.name}',
                                date=shipment.date,
                                shipment_id=shipment.id
                            )
                            db.session.add(addbalancerop)

        else:
            isPaid = IsPaidManagerBonus.query.filter_by(
                manager_name=manager.name, start_week=start_of_week).first()
            if isPaid and isPaid.isPaid:
                del_bonus = ManagerBalance.query.get_or_404(
                    isPaid.id_man_bonus)
                del_paid = IsPaidManagerBonus.query.get_or_404(isPaid.id)
                db.session.delete(del_bonus)
                db.session.delete(del_paid)
            if department.rop_percent > 0:
                RBalance = ManagerBalance.query.filter_by(comment = f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}", payment_type=f'Премия отгрузка менеджер {old_manager.name}').first()
                if RBalance:
                    db.session.delete(RBalance)



        for manager in dep_managers:
        # Считаем дельту менеджера за неделю
            shipments = Shipment.query.filter(
                Shipment.manager == manager.name,
                Shipment.date >= start_of_week,
                Shipment.date <= end_of_week
            ).all()
        
            manager_delta = sum(ship.delta for ship in shipments)
            manager_deltas[manager.id] = manager_delta
            total_delta += manager_delta

        if total_delta >= department.weekly_goal:
            isPaidDep = IsPaidDepartmentBonus.query.filter_by(department_id=department.id, start_week = start_of_week).first()
            if isPaidDep and isPaidDep.isPaid:
                for manager_id, delta in manager_deltas.items():
                    id_dep_bonus = ManagerBalance.query.filter_by(manager_id=manager_id, comment=f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}").first()
                    id_dep_bonus.amount = delta*(0.05)
                    db.session.flush()
            else:
                for manager_id, delta in manager_deltas.items():
                    balance_entry = ManagerBalance(
                        manager_id=manager_id,
                        amount=delta * 0.05,
                        comment=f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}",
                        payment_type='Бонус',
                        date=old_date
                    )
                    db.session.add(balance_entry)

                DepPaid = IsPaidDepartmentBonus(
                    department_id = department.id,
                    start_week = start_of_week,
                    isPaid=True
                )
                db.session.add(DepPaid)
        else:
            isPaidDep = IsPaidDepartmentBonus.query.filter_by(department_id=department.id, start_week = start_of_week).first()
            if isPaidDep and isPaidDep.isPaid:
                for manager_id, delta in manager_deltas.items():
                    all_dep_bonus = ManagerBalance.query.filter_by(manager_id=manager_id, comment=f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}").first()
                    del_dep_bonus = ManagerBalance.query.get_or_404(all_dep_bonus.id)
                    db.session.delete(del_dep_bonus) 
                    print(del_dep_bonus)
                del_dep_paid = IsPaidDepartmentBonus.query.get_or_404(isPaidDep.id)
                db.session.delete(del_dep_paid)


        db.session.commit()
        return redirect(url_for('shipments'))

    shipment_date_str = shipment.date.strftime('%Y-%m-%d')
    return render_template('metall/shipments/edit_shipment.html',
                           shipment=shipment,
                           managers=managers,
                           shipment_date_str=shipment_date_str)


@app.route('/shipments/<int:id>/delete', methods=['POST'])
@login_required
def delete_shipment(id):
    shipment = Shipment.query.get_or_404(id)
    manager = Manager.query.filter_by(name=shipment.manager).first()
    rop = Manager.query.filter_by(role='РОП', department_id=manager.department_id).first()
    department = Department.query.filter_by(id=manager.department_id).first()
    delMBalance = ManagerBalance.query.filter_by(shipment_id=id, payment_type='Отгрузка').first()
    delRBalance = ManagerBalance.query.filter_by(shipment_id=id, payment_type=f'Отгрузка менеджер {manager.name}').first()
    old_date = shipment.date

    forward = Manager.query.filter_by(name=shipment.forwarder_name).first()

    if forward:
        forwardPay = ManagerBalance.query.filter_by(manager_id=forward.id, payment_type='Экспедиторские', shipment_id=shipment.id).first()
        if forwardPay:
            delPay = ManagerBalance.query.get_or_404(forwardPay.id)
            db.session.delete(delPay)

    db.session.commit()

    db.session.delete(shipment)

    start_of_week = old_date - timedelta(days=old_date.weekday())
    end_of_week = start_of_week + timedelta(days=7)


    if manager:
        shipments_query = Shipment.query.filter_by(manager=manager.name)
        shipments_query = shipments_query.filter(
            Shipment.date >= start_of_week,
            Shipment.date <= end_of_week
        )
        period_shipments_sum = shipments_query.with_entities(
            func.sum(Shipment.delta)).scalar() or 0.0

        if period_shipments_sum >= manager.goal:
            isPaid = IsPaidManagerBonus.query.filter_by(
                manager_name=manager.name, start_week=start_of_week).first()
            if isPaid and isPaid.isPaid:
                bonus = ManagerBalance.query.get(isPaid.id_man_bonus)
                bonus.amount = (period_shipments_sum*0.05)
                if department.rop_percent > 0:
                    RBalance = ManagerBalance.query.filter_by(shipment_id=id, payment_type=f'Отгрузка менеджер {manager.name}').first()
                    if RBalance:
                        RBalance.amount = period_shipments_sum*0.015
            else:
                addBonusBalance = ManagerBalance(
                    manager_id=manager.id,
                    amount=period_shipments_sum*0.05,
                    comment=f"Бонус за закрытую личную цель. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}",
                    payment_type='Бонус',
                    date=old_date
                )
                db.session.add(addBonusBalance)
                db.session.flush()

                isPaidBonus = IsPaidManagerBonus(
                    manager_name=manager.name,
                    start_week=start_of_week,
                    isPaid=True,
                    id_man_bonus=addBonusBalance.id
                )
                db.session.add(isPaidBonus)
                if department.rop_percent > 0:
                    if rop:
                        if manager.role == 'Менеджер':
                            addbalancerop = ManagerBalance(
                                manager_id = rop.id,
                                amount = period_shipments_sum*0.015,
                                comment = f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}",
                                payment_type=f'Премия отгрузка менеджер {manager.name}',
                                date=old_date,
                                shipment_id=id
                            )
                            db.session.add(addbalancerop)

        else:
            isPaid = IsPaidManagerBonus.query.filter_by(
                manager_name=manager.name, start_week=start_of_week).first()
            if isPaid and isPaid.isPaid:
                del_new_bonus = ManagerBalance.query.get_or_404(
                    isPaid.id_man_bonus)
                del_new_paid = IsPaidManagerBonus.query.get_or_404(isPaid.id)
                db.session.delete(del_new_bonus)
                db.session.delete(del_new_paid)
            if department.rop_percent > 0:
                RBalance = ManagerBalance.query.filter_by(comment = f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}", payment_type=f'Премия отгрузка менеджер {manager.name}').first()
                if RBalance:
                    db.session.delete(RBalance)

    if delMBalance:
        del_bonus = ManagerBalance.query.get_or_404(delMBalance.id)
        db.session.delete(del_bonus)
    
    if delRBalance:
        del_bonus = ManagerBalance.query.get_or_404(delRBalance.id)
        db.session.delete(del_bonus)
    

 

    #удаление бонуса отдела при необходимости 
    department = Department.query.filter_by(id=manager.department_id).first()
    
    if department:
        dep_managers = Manager.query.filter_by(department_id = department.id).all()
        
    total_delta = 0
    manager_deltas = {}

    if department:
        for manager in dep_managers:
        # Считаем дельту менеджера за неделю
            shipments = Shipment.query.filter(
                Shipment.manager == manager.name,
                Shipment.date >= start_of_week,
                Shipment.date <= end_of_week
            ).all()
            
            manager_delta = sum(ship.delta for ship in shipments)
            manager_deltas[manager.id] = manager_delta
            total_delta += manager_delta
        
        if total_delta >= department.weekly_goal:
            isPaidDep = IsPaidDepartmentBonus.query.filter_by(department_id=department.id, start_week = start_of_week).first()
            if isPaidDep and isPaidDep.isPaid:
                for manager_id, delta in manager_deltas.items():
                    id_dep_bonus = ManagerBalance.query.filter_by(manager_id=manager_id, comment=f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}").first()
                    id_dep_bonus.amount = delta*(0.05)
                    db.session.flush()
            else:
                for manager_id, delta in manager_deltas.items():
                    balance_entry = ManagerBalance(
                        manager_id=manager_id,
                        amount=delta * 0.05,
                        comment=f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}",
                        payment_type='Бонус',
                        date=old_date
                    )
                    db.session.add(balance_entry)

                DepPaid = IsPaidDepartmentBonus(
                    department_id = department.id,
                    start_week = start_of_week,
                    isPaid=True
                )
                db.session.add(DepPaid)
        else:
            isPaidDep = IsPaidDepartmentBonus.query.filter_by(department_id=department.id, start_week = start_of_week).first()
            if isPaidDep and isPaidDep.isPaid:
                for manager_id, delta in manager_deltas.items():
                    all_dep_bonus = ManagerBalance.query.filter_by(manager_id=manager_id, comment=f"Бонус за закрытую цель отдела. c {start_of_week.strftime('%d.%m.%Y')} по {end_of_week.strftime('%d.%m.%Y')}").first()
                    del_dep_bonus = ManagerBalance.query.get_or_404(all_dep_bonus.id)
                    db.session.delete(del_dep_bonus) 
                    print(del_dep_bonus)
                del_dep_paid = IsPaidDepartmentBonus.query.get_or_404(isPaidDep.id)
                db.session.delete(del_dep_paid)

    db.session.commit()
    return redirect(url_for('shipments'))


@app.route('/export_shipments', methods=['GET'])
@login_required
def export_shipments():
    # Применяем те же фильтры, что и в /shipments
    manager_filter = request.args.get('manager')
    period_filter = request.args.get('period', 'all')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = Shipment.query

    if manager_filter:
        query = query.filter_by(manager=manager_filter)

    today = datetime.utcnow().date()
    if period_filter == 'month':
        first_day = today.replace(day=1)
        last_day = (first_day + timedelta(days=32)
                    ).replace(day=1) - timedelta(days=1)
        query = query.filter(Shipment.date.between(first_day, last_day))
    elif period_filter == 'week':
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=7)
        query = query.filter(Shipment.date.between(monday, sunday))
    elif period_filter == 'custom' and start_date and end_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Shipment.date.between(start, end))
        except ValueError:
            pass

    shipments = query.order_by(Shipment.date.desc()).all()

    # Создаем DataFrame
    data = [{
        'ID': ship.id,
        'Месяц': ship.month,
        'Неделя': ship.week,
        'Дата': ship.date.strftime('%Y-%m-%d'),
        'Менеджер': ship.manager,
        'ID сделки': ship.deal_id,
        'Поставщик': ship.supplier,
        'Служба доставки': ship.delivery_service,
        'Адрес': ship.address,
        'Источник': ship.source,
        'Телефон': ship.client_phone,
        'Класс': ship.is_class,
        'Клиент': ship.client_name,
        'Товар': ship.product,
        'Оплата клиента': ship.client_payment,
        'Оплата поставщику': ship.supplier_payment,
        'Логистика': ship.logistics,
        'Налог': ship.tax,
        'Оплата экспедитору': ship.forwarder_payment,
        'Другие расходы': ship.other_expenses,
        'Дельта': ship.delta,
        'Экспедитор': ship.forwarder_name,
        'Упд доставка(ссылка)': ship.upd_logistic,
        'Упд товар(ссылка)': ship.upd_product,
    } for ship in shipments]

    df = pd.DataFrame(data)

    # Создаем Excel файл в памяти
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Отгрузки')

    output.seek(0)

    # Формируем имя файла с текущей датой
    current_date = datetime.now().strftime("%Y-%m-%d")
    filename = f"Отгрузки_{current_date}.xlsx"

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )





# --- Аналитика ---
@app.route('/analytics')
@login_required
def analytics():
    # Статистика по менеджерам
    manager_stats = db.session.query(
        Shipment.manager,
        func.sum(Shipment.delta).label('total_delta'),
        func.avg(Shipment.delta).label('avg_delta'),
        func.count(Shipment.id).label('shipment_count')
    ).group_by(Shipment.manager).all()

    # Дельта по месяцам
    monthly_delta = db.session.query(
        Shipment.month,
        func.sum(Shipment.delta).label('total_delta')
    ).group_by(Shipment.month).order_by(Shipment.month).all()

    # Средние показатели
    avg_values = {
        'client_payment': db.session.query(func.avg(Shipment.client_payment)).scalar() or 0,
        'delta': db.session.query(func.avg(Shipment.delta)).scalar() or 0,
        'logistics': db.session.query(func.avg(Shipment.logistics)).scalar() or 0,
    }

    return render_template('metall/analytics.html',
                           manager_stats=manager_stats,
                           monthly_delta=monthly_delta,
                           avg_values=avg_values)


@app.route('/analytics/chart/monthly_delta')
@login_required
def monthly_delta_chart():
    monthly_delta = db.session.query(
        Shipment.month,
        func.sum(Shipment.delta).label('total_delta')
    ).group_by(Shipment.month).order_by(Shipment.month).all()

    months = [item[0] for item in monthly_delta]
    deltas = [float(item[1]) for item in monthly_delta]

    return jsonify({
        'months': months,
        'deltas': deltas
    })


@app.route('/analytics/chart/manager_performance')
@login_required
def manager_performance_chart():
    manager_stats = db.session.query(
        Shipment.manager,
        func.sum(Shipment.delta).label('total_delta')
    ).group_by(Shipment.manager).all()

    managers = [item[0] for item in manager_stats]
    deltas = [float(item[1]) for item in manager_stats]

    return jsonify({
        'managers': managers,
        'deltas': deltas
    })





# --- Общие функции ---
@app.template_filter('delta_class')
def delta_class_filter(value):
    if value > 0:
        return 'text-success'
    elif value < 0:
        return 'text-danger'
    return ''


def create_tables():
    """Отдельная функция для создания таблиц"""
    with app.app_context():
        db.create_all()
        # Создаем категорию ФОТ, если ее нет
        if not Categories.query.filter_by(naming='ФОТ').first():
            fot_category = Categories(naming='ФОТ')
            db.session.add(fot_category)
            db.session.commit()

        if not Department.query.filter_by(name="Менеджеры без отдела").first():
            dep = Department(name='Менеджеры без отдела', weekly_goal=1000000000)
            db.session.add(dep)
            db.session.commit()
  





# --- Запуск ---
if __name__ == '__main__':
    #create_tables()
    app.run(host='0.0.0.0', debug=False, port=8000)
