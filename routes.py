from flask import render_template, redirect, url_for, flash, request, session, jsonify, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, MainUser
from utils import get_user_db
from config import USER_DB_FOLDER
from sqlalchemy import create_engine
from datetime import datetime,timedelta
import os, json, io
import pandas as pd
from flask import request, jsonify
from flask_login import login_required
from flask import render_template

login_manager = LoginManager()
login_manager.login_view = "login"

def init_routes(app):
    login_manager.init_app(app)

#=========================== LOGIN MANAGER ===========================#

    @login_manager.user_loader
    def load_user(user_id):
        return MainUser.query.get(int(user_id))
    
#=========================== STRING FORMAT ===========================#

    @app.template_filter()
    def rupiah(value):
        try:
            return "Rp {:,.0f}".format(int(value)).replace(",", ".")
        except:
            return "Rp 0"
        
    @app.template_filter()
    def percent(value):
        try:
            return "{:.0f}%".format(float(value))
        except:
            return "0%"

#=========================== HOME ===========================#
    @app.route("/")
    def home():
        if current_user.is_authenticated:
            return render_template("index.html")  # tampilkan halaman utama
        else:
            return redirect(url_for("login"))

#=========================== REGISTER ===========================#

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            username = request.form["username"].strip()
            password = generate_password_hash(request.form["password"])

            # Cek username sudah ada
            if MainUser.query.filter_by(username=username).first():
                flash("Username sudah ada!")
                return redirect(url_for("register"))

            # Simpan user baru di main DB
            new_user = MainUser(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()

            # Buat DB user baru
            user_db_path = os.path.join(USER_DB_FOLDER, f"{username}.db")
            engine = create_engine(f"sqlite:///{user_db_path}")

            from models import UserProduct, UserTransaction, InvoiceTemplate, UserCashier

            # Buat semua tabel
            UserProduct.metadata.create_all(engine)
            UserTransaction.metadata.create_all(engine)
            InvoiceTemplate.metadata.create_all(engine)
            UserCashier.metadata.create_all(engine)

            # Pastikan kolom baru ada (jika model diperbarui)
            with engine.connect() as conn:
                try:
                    conn.execute("ALTER TABLE user_transaction ADD COLUMN status VARCHAR(20) DEFAULT 'draft'")
                except Exception:
                    pass  # jika sudah ada, lanjut

                try:
                    conn.execute("ALTER TABLE invoice_template ADD COLUMN barcode_link VARCHAR(300)")
                except Exception:
                    pass

                try:
                    conn.execute("ALTER TABLE invoice_template ADD COLUMN show_barcode BOOLEAN DEFAULT 1")
                except Exception:
                    pass

            flash("Berhasil register! Silahkan login.")
            return redirect(url_for("login"))

        return render_template("register.html")

    
#=========================== LOGIN ===========================#

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]

            user = MainUser.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                login_user(user)
                session["user_db"] = os.path.join(USER_DB_FOLDER, f"{username}.db")
                flash("Login berhasil!", "success")
                return redirect(url_for("dashboard"))

            flash("Username atau password salah!","Peringatan!")
        return render_template("login.html")
    
#=========================== LOGOUT ===========================#

    @app.route("/logout")
    @login_required
    def logout():
        username = current_user.username  # ambil nama user yang sedang login
        logout_user()
        flash(f"Hi {username}, sampai jumpa lagi!", "Berhasil Logout")
        return redirect(url_for("login"))
    
  #=========================== PRODUCTS ===========================#

    @app.route("/products", methods=["GET", "POST"])
    @login_required
    def products():
        user_app, user_db, UserProduct, UserTransaction = get_user_db()
        if not user_db:
            flash("DB user tidak ditemukan!","warning")
            return redirect(url_for("login"))

        if request.method == "POST":
            name = request.form["name"].strip()
            price_input = request.form["price"].replace(".", "").replace(",", "")
            price = int(price_input)
            stock = int(request.form["stock"])
            new_product = UserProduct(name=name, price=price, stock=stock)
            user_db.add(new_product)
            user_db.commit()
            flash("Produk berhasil ditambahkan!","success")

        products_list = user_db.query(UserProduct).all()
        return render_template("products.html", products=products_list)
        #===================================================================

    @app.route("/add_product_page")
    @login_required
    def add_product_page():
        return render_template("add_product.html")

        #===================================================================
    @app.route("/edit_product/<int:product_id>", methods=["GET", "POST"])
    @login_required
    def edit_product(product_id):
        user_app, user_db, UserProduct, UserTransaction = get_user_db()
        if not user_db:
            flash("DB user tidak ditemukan!", "warning")
            return redirect(url_for("products"))

        product = user_db.get(UserProduct, product_id)
        if not product:
            flash("Produk tidak ditemukan!", "warning")
            return redirect(url_for("products"))

        if request.method == "POST":
            product.name = request.form["name"].strip()

            # harga
            price_input = request.form["price"].replace(".", "").replace(",", "")
            product.price = int(price_input)

            # stok lama
            current_stock = product.stock or 0

            # update stok:
            # - field "stock" digunakan untuk edit total stok langsung
            # - field "add_stock" digunakan untuk menambah stok ke stok lama
            base_stock = int(request.form.get("stock", current_stock))
            add_stock = int(request.form.get("add_stock", 0))

            new_stock = base_stock + add_stock

            # validasi stok tidak boleh negatif
            if new_stock < 0:
                flash("Stok tidak boleh kurang dari 0.", "warning")
                return redirect(url_for("edit_product", product_id=product.id))


            product.stock = new_stock
            user_db.commit()

            flash(f"Produk '{product.name}' berhasil diperbarui!", "success")
            return redirect(url_for("products"))

        return render_template("edit_product.html", product=product)

    
    #===============================================================================

    @app.route("/delete_product/<int:product_id>", methods=["POST"])
    @login_required
    def delete_product(product_id):
        user_app, user_db, UserProduct, UserTransaction = get_user_db()
        if not user_db:
            flash("DB user tidak ditemukan!","error")
            return redirect(url_for("products"))

        product = user_db.get(UserProduct, product_id)
        if not product:
            flash("Produk tidak ditemukan!","error")
            return redirect(url_for("products"))

        user_db.delete(product)
        user_db.commit()
        flash(f"Produk '{product.name}' berhasil dihapus!","success")
        return redirect(url_for("products"))

#=========================== FILTER RUPIAH ===========================#

    @app.template_filter("rupiah")
    def rupiah_format(value):
        try:
            value = float(value)
            return "Rp {:,.2f}".format(value).replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return value
#=========================== EXPORT TRANSCATIONS ===========================#

    @app.route("/export_transactions")
    @login_required
    def export_transactions():
        import io
        import pandas as pd
        import json
        from flask import send_file, flash, redirect, url_for

        # Ambil session & model user
        user_app, user_db, UserProduct, UserTransaction = get_user_db()
        if not user_db:
            flash("DB user tidak ditemukan!")
            return redirect(url_for("login"))

        # Query semua transaksi
        transactions = user_db.query(UserTransaction).all()
        data = []
        for tx in transactions:
            items = json.loads(tx.items) if tx.items else []
            discount_value = float(tx.discount or 0)
            total_after_discount = (tx.subtotal or 0) - ((tx.subtotal or 0) * discount_value / 100)
            change = (tx.paid or 0) - total_after_discount

            for item in items:
                item_subtotal = int(item.get("qty", 0)) * float(item.get("price", 0))
                item_diskon_rp = item_subtotal * discount_value / 100
                item_netto = item_subtotal - item_diskon_rp

                data.append({
                    "ID": tx.id,
                    "Tanggal": tx.created_at.strftime("%d-%m-%Y") if tx.created_at else "",
                    "Jam": tx.created_at.strftime("%H:%M") if tx.created_at else "",
                    "Produk": item.get("name"),
                    "Qty": item.get("qty"),
                    "Harga": item.get("price"),
                    "Total": item_subtotal,
                    "(%)": f"{int(discount_value)}%",
                    "Diskon": item_diskon_rp,
                    "Subtotal": item_netto,
                    "Bayar": tx.paid,
                    "Kembali": change,
                    "Kasir": getattr(tx, "kasir_name", "Unknown"),
                    "Status": getattr(tx, "status", "")
                })

        # Buat DataFrame
        df = pd.DataFrame(data)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Transaksi")
            workbook  = writer.book
            worksheet = writer.sheets["Transaksi"]

            # ================= HEADER =================
            header_center = workbook.add_format({
                'bold': True, 'bg_color': '#D9E1F2',
                'align': 'center', 'border': 1
            })
            header_left = workbook.add_format({
                'bold': True, 'bg_color': '#D9E1F2',
                'align': 'left', 'border': 1
            })
            header_right = workbook.add_format({
                'bold': True, 'bg_color': '#D9E1F2',
                'align': 'right', 'border': 1
            })

            headers = [
                "ID", "Tanggal", "Jam", "Produk", "Qty", "Harga", "Total",
                "(%)", "Diskon", "Subtotal", "Bayar", "Kembali", "Kasir", "Status"
            ]

            for col_num, col_name in enumerate(headers):
                if col_name in ["ID", "Tanggal", "Jam", "Qty", "(%)", "Status"]:
                    worksheet.write(0, col_num, col_name, header_center)
                elif col_name in ["Produk"]:
                    worksheet.write(0, col_num, col_name, header_left)
                else:
                    col_name in ["Kasir"]
                    worksheet.write(0, col_num, col_name, header_right)

            # ================= FORMAT ISI =================
            center_format     = workbook.add_format({'align': 'center'})
            left_format       = workbook.add_format({'align': 'left'})
            right_num_format  = workbook.add_format({'num_format': '#,##0', 'align': 'right'})
            right_text_format = workbook.add_format({'align': 'right'})

            # Selang-seling warna (abu muda)
            alt_center = workbook.add_format({'align': 'center', 'bg_color': '#F9F9F9'})
            alt_left   = workbook.add_format({'align': 'left',   'bg_color': '#F9F9F9'})
            alt_right_num  = workbook.add_format({'num_format': '#,##0', 'align': 'right', 'bg_color': '#F9F9F9'})
            alt_right_text = workbook.add_format({'align': 'right', 'bg_color': '#F9F9F9'})

            # ================= SET WIDTH =================
            worksheet.set_column("A:A", 6)   # ID
            worksheet.set_column("B:B", 12)  # Tanggal
            worksheet.set_column("C:C", 8)   # Jam
            worksheet.set_column("D:D", 30)  # Produk
            worksheet.set_column("E:E", 6)   # Qty
            worksheet.set_column("F:F", 12)  # Harga
            worksheet.set_column("G:G", 12)  # Total
            worksheet.set_column("H:H", 7)   # (%)
            worksheet.set_column("I:I", 10)  # Diskon
            worksheet.set_column("J:J", 12)  # Subtotal
            worksheet.set_column("K:K", 12)  # Bayar
            worksheet.set_column("L:L", 12)  # Kembali
            worksheet.set_column("M:M", 15)  # Kasir
            worksheet.set_column("N:N", 15)  # Status

            # ================= TULIS DATA =================
            last_id = None
            use_alt = False
            for row_num, row in enumerate(df.itertuples(index=False), start=1):
                if row[0] != last_id:  # kolom 0 = ID
                    use_alt = not use_alt
                    last_id = row[0]

                for col_num, col_name in enumerate(headers):
                    value = row[col_num]  # akses via index, bukan nama kolom

                    if col_name in ["Produk"]:
                        fmt = alt_left if use_alt else left_format
                    elif col_name in ["ID", "Tanggal", "Jam", "Qty", "(%)", "Status"]:
                        fmt = alt_center if use_alt else center_format
                    else:
                        if col_name in ["Harga", "Total", "Diskon", "Subtotal", "Bayar", "Kembali","Kasir"]:
                            fmt = alt_right_num if use_alt else right_num_format
                        else:
                            fmt = alt_right_text if use_alt else right_text_format

                    worksheet.write(row_num, col_num, value, fmt)

        output.seek(0)
        return send_file(
            output,
            download_name="transaksi.xlsx",
            as_attachment=True,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


#=========================== FORM TAMBAH PRODUCT ===========================#

    @app.route('/add_product', methods=['GET'])
    @login_required
    def add_product_form():
        return render_template('add_product.html')


    @app.route('/add_product', methods=['POST'])
    @login_required
    def add_product():
        name = request.form['name'].strip()
        price_input = request.form['price'].replace('.', '').replace(',', '')
        price = int(price_input)
        stock = int(request.form['stock'])

        # Ambil DB user
        user_engine, user_db, UserProduct, UserTransaction = get_user_db()
        if not user_db:
            flash("DB user tidak ditemukan!")
            return redirect(url_for("products"))

        # Buat objek produk baru dan simpan
        new_product = UserProduct(name=name, price=price, stock=stock)
        user_db.add(new_product)
        user_db.commit()

        flash(f"Produk '{name}' berhasil ditambahkan!","success")
        return redirect(url_for('products'))

#=========================== API PRODUCTS ===========================#

    @app.route('/api/products/search')
    @login_required
    def api_search_products():
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify([])

        # Ambil database user
        engine, db_session, UserProduct, UserTransaction = get_user_db()
        if not db_session:
            return jsonify([])

        # Filter produk sesuai query
        products = db_session.query(UserProduct).filter(UserProduct.name.ilike(f"%{query}%")).all()

        results = []
        for p in products:
            results.append({
                "id": p.id,
                "name": p.name,
                "price": p.price,
                "stock": p.stock,
                "sold": p.sold or 0
            })

        return jsonify(results)
    
#=========================== RESET ===========================#

    @app.route("/reset", methods=["GET"])
    @login_required
    def reset_page():

        return render_template("reset.html")
    # API Reset Data

    @app.route("/reset/<string:type>", methods=["POST"])
    @login_required
    def reset_data(type):
        user_app, user_db, UserProductModel, UserTransactionModel = get_user_db()

        try:
            if type == "transaction":
                deleted_count = user_db.query(UserTransactionModel).delete()
                user_db.commit()
                flash(f"✅ Semua transaksi ({deleted_count}) berhasil dihapus!", "success")

            elif type == "product":
                deleted_count = user_db.query(UserProductModel).delete()
                user_db.commit()
                flash(f"✅ Semua produk ({deleted_count}) berhasil dihapus!", "success")

            else:
                flash("Tipe data tidak valid!", "warning")
                return redirect(url_for("dashboard"))

            # Setelah reset, redirect ke halaman dashboard atau halaman lain sesuai kebutuhan
            return redirect(url_for("dashboard"))

        except Exception as e:
            user_db.rollback()
            flash(f"Gagal menghapus data: {str(e)}", "error")
            return redirect(url_for("dashboard"))

#=========================== DASHBOARD ===========================#

    from flask import render_template, jsonify, redirect, url_for
    from flask_login import current_user
    from sqlalchemy import func
    from utils import get_user_db
    from datetime import datetime
    import json

    @app.route("/dashboard")
    @login_required
    def dashboard():
        user_app, user_db, UserProduct, UserTransaction = get_user_db()
        if not user_app:
            return redirect(url_for("login"))

        total_products = user_db.query(UserProduct).count()
        total_transactions = user_db.query(UserTransaction).count()
        total_revenue = user_db.query(func.sum(UserTransaction.total)).scalar() or 0

        return render_template("dashboard.html",
                            username=current_user.username,
                            total_products=total_products,
                            total_transactions=total_transactions,
                            total_revenue=total_revenue)
    
#=========================== CHART DATA ===========================#
    from flask import jsonify
    from sqlalchemy import func
    from datetime import datetime
    import json

    @app.route("/chart-data")
    @login_required
    def chart_data_view():
        user_app, user_db, UserProduct, UserTransaction = get_user_db()
        if not user_app:
            return jsonify({})

        # --- Total Produk & Transaksi & Revenue ---
        total_products = user_db.query(UserProduct).count()
        total_transactions = user_db.query(UserTransaction).count()
        total_revenue = user_db.query(func.sum(UserTransaction.total)).scalar() or 0

        # --- Sales Per Hour (0-23) hari ini ---
        hourly_sales = [0]*24
        today_start = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        transactions_today = user_db.query(UserTransaction).filter(
            UserTransaction.created_at >= today_start
        ).all()
        for tx in transactions_today:
            hour = tx.created_at.hour
            hourly_sales[hour] += tx.total or 0
        hourly_labels = [str(h) for h in range(24)]

        # --- Daily Revenue (1-31) bulan ini ---
        daily_revenue = [0]*31
        for tx in transactions_today:
            day = tx.created_at.day - 1
            daily_revenue[day] += tx.total or 0
        daily_revenue_labels = [str(d+1) for d in range(31)]

        # --- Top Products (dari items di transaksi) ---
        product_counter = {}
        transactions = user_db.query(UserTransaction).all()
        for tx in transactions:
            try:
                items = json.loads(tx.items) if tx.items else []
                for item in items:
                    name = item.get("name")
                    qty = int(item.get("qty", 0))
                    product_counter[name] = product_counter.get(name, 0) + qty
            except Exception:
                continue
        top_labels = list(product_counter.keys())[:5]
        top_sales = list(product_counter.values())[:5]

        return jsonify({
            "total_products": total_products,
            "total_transactions": total_transactions,
            "total_revenue": total_revenue,
            "hourly_labels": hourly_labels,
            "hourly_sales": hourly_sales,
            "daily_revenue_labels": daily_revenue_labels,
            "daily_revenue": daily_revenue,
            "top_products_labels": top_labels,
            "top_products_sales": top_sales,
        })

#=========================== BARCODE EDIT ===========================#

    from flask import render_template, request, flash, redirect, url_for
    from flask_login import current_user
    from utils import get_user_db
    from models import InvoiceTemplate

    @app.route("/barcode/edit", methods=["GET"])
    @login_required
    def edit_barcode():
        # Ambil session & model user
        user_app, user_db, _, _, InvoiceTemplateModel = get_user_db(include_template=True)
        if not user_db:
            flash("DB user tidak ditemukan!", "danger")
            return redirect(url_for("dashboard"))

        # Ambil template QR untuk user saat ini
        template = user_db.query(InvoiceTemplateModel).filter_by(user_id=current_user.id).first()
        if not template:
            # Jika belum ada, buat record baru
            template = InvoiceTemplateModel(user_id=current_user.id)
            user_db.add(template)
            user_db.commit()

        barcode_link = getattr(template, "barcode_link", "")
        return render_template("edit_barcode.html", barcode_link=barcode_link)
    
#=========================== BARCODE UPDATE ===========================#

    @app.route("/barcode/update", methods=["POST"])
    @login_required
    def update_transaction_barcode():
        user_app, user_db, _, _, InvoiceTemplateModel = get_user_db(include_template=True)
        if not user_db:
            flash("DB user tidak ditemukan!", "danger")
            return redirect(url_for("dashboard"))

        template = user_db.query(InvoiceTemplateModel).filter_by(user_id=current_user.id).first()
        if not template:
            template = InvoiceTemplateModel(user_id=current_user.id)
            user_db.add(template)
            user_db.commit()

        barcode_link = request.form.get("barcode_link", "").strip()
        if not barcode_link:
            flash("Link QR Code tidak boleh kosong!", "danger")
            return redirect(url_for("edit_barcode"))

        template.barcode_link = barcode_link
        user_db.commit()
        flash("QR Code berhasil diperbarui ✅", "success")
        return redirect(url_for("edit_barcode"))
    
#=========================== GENERATE QRCODE ===========================#   

    @app.route("/generate_qrcode_tx")
    @login_required
    def generate_qrcode_tx():
        from flask import send_file
        import qrcode, io

        data = request.args.get("data", "")
        if not data:
            return "", 400

        img = qrcode.make(data)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png")
    
#=========================== EDIT INVOICE ===========================#
    from datetime import datetime

    @app.route("/edit-invoice", methods=["GET", "POST"])
    @login_required
    def edit_invoice():
        user_app, user_db, UserProduct, UserTransaction, InvoiceTemplate = get_user_db(include_template=True)
        if not user_db:
            flash("DB user tidak ditemukan!")
            return redirect(url_for("login"))

        template = user_db.query(InvoiceTemplate).filter_by(user_id=current_user.id).first()
        if not template:
            template = InvoiceTemplate(user_id=current_user.id)
            user_db.add(template)
            user_db.commit()


        if request.method == "POST":
            template.store_name = request.form.get("storeName", template.store_name)
            template.store_address = request.form.get("storeAddress", template.store_address)
            template.footer_note = request.form.get("footerNote", template.footer_note)
            user_db.commit()
            flash("Template invoice berhasil diperbarui!","success")
            return redirect(url_for("edit_invoice"))
            
        return render_template("edit_invoice.html", template=template, created_at=datetime.now())
    
#=========================== LAYANAN PELANGGAN ===========================#

    @app.route("/layanan-pelanggan")
    @login_required
    def layanan_pelanggan():
        return render_template("layanan-pelanggan.html")

#=========================== EKSPORT PRODUCT ===========================#

    @app.route("/export_products")
    @login_required
    def export_products():
        import io
        import pandas as pd

        user_app, user_db, UserProduct, UserTransaction = get_user_db()
        if not user_db:
            flash("DB user tidak ditemukan!")
            return redirect(url_for("products"))

        # Ambil data produk
        products = user_db.query(UserProduct).all()
        data = []
        for p in products:
            sisa = (p.stock or 0) - (p.sold or 0)
            data.append({
                "No.": p.id,
                "Nama Produk": p.name,
                "Harga": p.price,
                "Stok": p.stock,
                "Terjual": p.sold,
                "Stok Sisa": sisa
            })

        df = pd.DataFrame(data)

        # Buat output Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Products")
            workbook  = writer.book
            worksheet = writer.sheets["Products"]

            # Format header
            header_left = workbook.add_format({
                'bold': True,
                'bg_color': '#D9E1F2',
                'border': 1,
                'align': 'left',
                'valign': 'vcenter'
            })
            header_center = workbook.add_format({
                'bold': True,
                'bg_color': '#D9E1F2',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })

            for col_num, value in enumerate(df.columns.values):
                if col_num == 1:  # Nama Produk (B)
                    worksheet.write(0, col_num, value, header_left)
                else:
                    worksheet.write(0, col_num, value, header_center)

                    # Format header
            header_center = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'align': 'center', 'valign': 'vcenter', 'border':1})
            header_left   = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'align': 'left',   'valign': 'vcenter', 'border':1})
            header_right  = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'align': 'right',  'valign': 'vcenter', 'border':1, 'num_format': '#,##0'})

            # Format data
            center_format = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
            left_format   = workbook.add_format({'align': 'left',   'valign': 'vcenter'})
            right_format  = workbook.add_format({'align': 'right',  'valign': 'vcenter', 'num_format': '#,##0'})

            # Set header
            worksheet.write(0, 0, "No.", header_center)
            worksheet.write(0, 1, "Nama Produk", header_left)
            worksheet.write(0, 2, "Harga", header_right)
            worksheet.write(0, 3, "Stok", header_right)
            worksheet.write(0, 4, "Terjual", header_right)
            worksheet.write(0, 5, "Stok Sisa", header_right)

            # Set kolom data
            worksheet.set_column("A:A", 6, center_format)    # No.
            worksheet.set_column("B:B", 30, left_format)     # Nama Produk
            worksheet.set_column("C:F", 12, right_format)    # Harga, Stok, Terjual, Stok Sisa


        output.seek(0)

        return send_file(
            output,
            download_name="products.xlsx",
            as_attachment=True,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
   
#=========================== POS TEMP ===========================#

    @app.route("/pos/process_temp", methods=["POST"])
    @login_required
    def pos_process_temp():
        data = request.get_json()
        if not data:
            return {"status":"error","message":"Data transaksi kosong"}, 400

        cart = data.get("cart", [])
        discount = int(data.get("discount",0))
        paid = int(data.get("paid",0))
        kasir_name = data.get("kasir_name", "UNKNOWN")  # ambil nama kasir

        user_app, user_db, UserProduct, UserTransaction, InvoiceTemplate = get_user_db(include_template=True)
        if not user_db:
            return {"status":"error","message":"DB user tidak ditemukan"}, 400

        items = []
        subtotal = 0
        for c in cart:
            product = user_db.get(UserProduct, int(c["id"]))
            qty = int(c["qty"])
            item_subtotal = product.price * qty
            subtotal += item_subtotal
            items.append({
                "id": product.id,
                "name": product.name,
                "qty": int(qty),
                "price": float(product.price),
                "subtotal": item_subtotal
            })

        total = float(subtotal) * (100 - float(discount))/100
        change = float(paid) - total if paid else 0

        template = user_db.query(InvoiceTemplate).filter_by(user_id=current_user.id).first()
        if not template:
            template = InvoiceTemplate(user_id=current_user.id)
            user_db.add(template)
            user_db.commit()

        barcode_link = template.barcode_link or ""

        return render_template("invoice-temp.html",
            tx_id="TEMP",
            created_at=datetime.now(),
            items=items,
            subtotal=subtotal,
            discount=discount,
            total=total,
            paid=paid,
            change=change,
            template=template,
            kasir_name=kasir_name,  # kirim ke template
            barcode_link=barcode_link
        )

#=========================== GENERATE BARCODE TEMP ===========================#

    @app.route("/generate_barcode_temp")
    @login_required
    def generate_barcode_temp():
        import io
        import qrcode
        from flask import send_file, request

        barcode_value = request.args.get("barcode")
        if not barcode_value:
            return "No barcode provided", 400

        # generate QR code image
        qr = qrcode.QRCode(
            version=1,       # ukuran QR (1 kecil, 40 besar)
            box_size=4,      # besar tiap kotak QR
            border=2         # margin putih di sekitar QR
        )
        qr.add_data(barcode_value)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return send_file(buffer, mimetype="image/png")


#=====================INVOICE BARCODE========================================#

    @app.route("/invoice_by_barcode/<string:barcode_link>")
    @login_required
    def invoice_by_barcode(barcode_link):
        size = request.args.get("size", "58")  # default 58mm
        user_app, user_db, UserProduct, UserTransaction, InvoiceTemplate = get_user_db(include_template=True)
        if not user_db:
            flash("DB user tidak ditemukan!", "danger")
            return redirect(url_for("login"))

        # Ambil template berdasarkan barcode_link
        template = user_db.query(InvoiceTemplate).filter_by(barcode_link=barcode_link, user_id=current_user.id).first()
        if not template:
            flash("Invoice tidak ditemukan!", "danger")
            return redirect(url_for("pos"))

        # Ambil transaksi terkait dari user_id/tx_id
        tx = user_db.query(UserTransaction).get(template.user_id)
        if not tx:
            flash("Transaksi tidak ditemukan!", "danger")
            return redirect(url_for("pos"))

        # Hitung subtotal, total, kembalian
        items = json.loads(tx.items) if tx.items else []
        for item in items:
            item["subtotal"] = item.get("price", 0) * item.get("qty", 0)

        subtotal = sum(item["subtotal"] for item in items)
        discount = tx.discount or 0
        total = subtotal * (100 - discount) / 100
        paid = tx.paid or 0
        change = paid - total

        # Pilih template HTML sesuai ukuran
        template_name = "invoice-80mm.html" if size == "80" else "invoice-58mm.html"

        return render_template(template_name,
            tx_id=tx.id,
            created_at=tx.created_at,
            items=items,
            subtotal=subtotal,
            discount=discount,
            total=total,
            paid=paid,
            change=change,
            template=template,
            size=size
        )

#====================CASHIER USER=================================#

    from models import UserCashier  # pastikan diimport

    @app.route("/cashiers", methods=["GET"])
    @login_required
    def cashiers():
        # Ambil session DB user aktif
        user_app, user_db, _, _ = get_user_db(include_template=False)
        
        # Query semua kasir dari tabel UserCashier
        cashiers = user_db.query(UserCashier).all()
        
        return render_template("cashiers.html", cashiers=cashiers)

    
    @app.route("/cashiers/add", methods=["POST"])
    @login_required
    def add_cashier():
        user_app, user_db, _, _ = get_user_db(include_template=False)  # ambil session saja
        name = request.form.get("name", "").strip()
        
        if not name:
            flash("Nama kasir tidak boleh kosong")
            return redirect(url_for("cashiers"))
        
        # Gunakan model UserCashier yang diimport
        if user_db.query(UserCashier).filter_by(name=name).first():
            flash("Nama kasir sudah ada")
            return redirect(url_for("cashiers"))
        
        new_cashier = UserCashier(name=name)
        user_db.add(new_cashier)
        user_db.commit()
        
        flash(f"Kasir '{name}' berhasil ditambahkan")
        return redirect(url_for("cashiers"))


    from models import UserCashier

    @app.route("/cashiers/delete/<int:cashier_id>", methods=["POST"])
    @login_required
    def delete_cashier(cashier_id):
        user_app, user_db, _, _ = get_user_db(include_template=False)  # session DB saja
        cashier = user_db.query(UserCashier).filter_by(id=cashier_id).first()
        
        if cashier:
            user_db.delete(cashier)
            user_db.commit()
            flash(f"Kasir '{cashier.name}' berhasil dihapus")
        else:
            flash(f"Kasir ID {cashier_id} tidak ditemukan")

        return redirect(url_for("cashiers"))


#=========================== POS HTML ===========================#
    from flask import render_template, request, jsonify, flash, redirect, url_for
    from flask_login import current_user
    from models import UserCashier, UserProduct, UserTransaction, InvoiceTemplate
    from utils import get_user_db
    from datetime import datetime
    import pytz, json

    # ================= POS =================
    @app.route("/pos", methods=["GET"])
    @login_required
    def pos():
        user_app, user_db, UserProduct, UserTransaction = get_user_db()
        if not user_db:
            flash("DB user tidak ditemukan!")
            return redirect(url_for("login"))

        products = user_db.query(UserProduct).all()
        cashiers = user_db.query(UserCashier).all()
        return render_template("pos.html", products=products, cashiers=cashiers)

    # ================== CREATE TRANSACTION DRAFT ==================
    # ================== CREATE TRANSACTION DRAFT ================== 
    @app.route("/pos/create_transaction", methods=["POST"])
    @login_required
    def pos_create_transaction():
        import json
        data = request.get_json()
        if not data:
            return {"status": "error", "message": "Tidak ada data"}, 400

        user_app, user_db, UserProduct, UserTransaction = get_user_db()
        if not user_db:
            return {"status": "error", "message": "DB user tidak ditemukan"}, 400

        items = data.get("items", [])
        discount_percent = float(data.get("discount", 0) or 0)
        paid = float(data.get("paid", 0) or 0)
        kasir_name = data.get("kasir_name")

        if not kasir_name:
            return {"status": "error", "message": "Kasir belum dipilih"}, 400

        # ----------------- Perhitungan ulang di server -----------------
        subtotal = 0
        clean_items = []
        for item in items:
            try:
                price = float(item.get("price", 0))
                qty = int(item.get("qty", 0))
                product = user_db.get(UserProduct, int(item.get("id")))
                if not product:
                    continue

                # Validasi stok real-time
                available_stock = max(0, (product.stock or 0) - (getattr(product, "sold", 0) or 0))
                if qty > available_stock:
                    return {
                        "status": "error",
                        "message": f"Stok {product.name} tidak cukup (tersisa {available_stock})"
                    }, 400

                line_subtotal = price * qty
                subtotal += line_subtotal

                clean_items.append({
                    "id": product.id,
                    "name": product.name,
                    "price": price,
                    "qty": qty
                })
            except Exception:
                continue

        discount_value = subtotal * (discount_percent / 100)
        total = subtotal - discount_value
        change = paid - total

        # ----------------- Simpan draft transaksi -----------------
        from datetime import datetime
        import pytz
        tz = pytz.timezone("Asia/Jakarta")
        created_at = datetime.now(tz)

        new_tx = UserTransaction(
            items=json.dumps(clean_items),
            subtotal=subtotal,
            discount=discount_percent,
            total=total,
            paid=paid,
            change=change,
            kasir_name=kasir_name,
            created_at=created_at,
            status="draft"
        )
        user_db.add(new_tx)
        user_db.commit()

        return {"status": "ok", "tx_id": new_tx.id}


    # ================== CONFIRM TRANSACTION ==================
    @app.route("/pos/confirm_transaction/<int:tx_id>", methods=["POST"])
    @login_required
    def confirm_transaction(tx_id):
        user_app, user_db, UserProduct, UserTransaction = get_user_db()
        if not user_db:
            return {"status": "error", "message": "DB user tidak ditemukan"}, 400

        tx = user_db.get(UserTransaction, tx_id)
        if not tx or tx.status != "draft":
            return {"status": "error", "message": "Transaksi tidak valid"}, 400

        import json
        items = json.loads(tx.items)

        for item in items:
            product = user_db.get(UserProduct, int(item["id"]))
            if not product:
                continue
            qty = int(item["qty"])

            # ✅ jangan kurangi stock
            # product.stock -= qty   ❌ hapus baris ini
            product.sold = (product.sold or 0) + qty   # cukup tambah sold

        tx.status = "confirmed"
        user_db.commit()

        return {"status": "ok", "tx_id": tx.id}



######################
    from flask import render_template
    from datetime import datetime

    @app.route("/invoice/<int:tx_id>")
    @login_required
    def invoice(tx_id):
        user_app, user_db, UserProduct, UserTransaction, InvoiceTemplate = get_user_db(include_template=True)
        tx = user_db.get(UserTransaction, tx_id)
        if not tx:
            flash("Transaksi tidak ditemukan!")
            return redirect(url_for("pos"))

        items = json.loads(tx.items) if tx.items else []

        template = user_db.query(InvoiceTemplate).filter_by(user_id=current_user.id).first()
        if not template:
            template = InvoiceTemplate(user_id=current_user.id)
            user_db.add(template)
            user_db.commit()

        return render_template("invoice-temp.html",
                            tx_id=tx.id,

                            created_at=tx.created_at or datetime.now(),

                            items=items,
                            subtotal=tx.subtotal,
                            discount=tx.discount,
                            total=tx.total,
                            paid=tx.paid,
                            change=tx.change,
                            kasir_name=tx.kasir_name,
                            template=template,
                            status=tx.status)
#=================INVOICE 58MM================================
# ===================== INVOICE 58MM =====================
    @app.route("/invoice-58mm/<int:tx_id>")
    @login_required
    def invoice_58mm(tx_id):
        # Ambil session & model untuk user
        user_app, user_db, UserProduct, UserTransaction, InvoiceTemplate = get_user_db(include_template=True)
        if not user_db:
            flash("DB user tidak ditemukan!")
            return redirect(url_for("login"))

        # Ambil transaksi
        tx = user_db.query(UserTransaction).get(tx_id)
        if not tx:
            flash("Transaksi tidak ditemukan!")
            return redirect(url_for("pos"))

        # Ambil item
        items = json.loads(tx.items) if tx.items else []
        for item in items:
            item["subtotal"] = item.get("price", 0) * item.get("qty", 0)

        # Hitung total & kembalian
        total = tx.subtotal - (tx.subtotal * (tx.discount or 0) / 100)
        change = (tx.paid or 0) - total

        # Ambil template invoice
        template = user_db.query(InvoiceTemplate).first()
        if not template:
            template = InvoiceTemplate()
            user_db.add(template)
            user_db.commit()

        # Render ke template 58mm
        return render_template(
            "invoice-58mm.html",
            tx_id=tx.id,
            created_at=tx.created_at,
            items=items,
            subtotal=tx.subtotal,
            discount=tx.discount or 0,
            total=total,
            paid=tx.paid or 0,
            change=change,
            kasir_name=session.get("kasir_name", "UNKNOWN"),
            status="confirmed",
            template=template
        )
