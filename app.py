from flask import Flask, redirect, render_template, session, jsonify, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Secret key for storing the user's cart session
app.secret_key = "food-ordering-secret-key"

# Database settings
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///food.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# Food item database table
class FoodItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(300))
    price = db.Column(db.Integer, nullable=False)
    image = db.Column(db.String(300))


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text, nullable=False)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="Pending", nullable=False)

    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)

    food_item_id = db.Column(db.Integer, db.ForeignKey("food_item.id"), nullable=False)

    quantity = db.Column(db.Integer, nullable=False)

    price = db.Column(db.Float, nullable=False)

    food_item = db.relationship("FoodItem")
    

@app.route("/")
def home():
    food_items = FoodItem.query.all()
    return render_template("index.html", food_items=food_items)


# Add food to cart
@app.route("/add-to-cart", methods=["POST"])
def add_to_cart():
    data = request.get_json()
    food_id = data.get("food_id")

    food = db.session.get(FoodItem, food_id)

    if not food:
        return jsonify({"error": "Food item not found"}), 404

    cart = session.get("cart", {})

    food_id = str(food.id)
    cart[food_id] = cart.get(food_id, 0) + 1

    session["cart"] = cart

    cart_count = sum(cart.values())

    cart_total = 0

    for item_id, quantity in cart.items():
        item = db.session.get(FoodItem, int(item_id))
        if item:
            cart_total += item.price * quantity

    return jsonify({
        "message": food.name + " added to cart",
        "cart_count": cart_count,
        "cart_total": cart_total
    })


with app.app_context():
    db.create_all()

@app.route("/cart")
def cart():
    cart = session.get("cart", {})

    cart_items = []
    cart_total = 0

    for item_id, quantity in cart.items():
        item = db.session.get(FoodItem, int(item_id))

        if item:
            item_total = item.price * quantity

            cart_items.append({
                "item": item,
                "quantity": quantity,
                "total": item_total
            })

            cart_total += item_total

    return render_template(
        "cart.html",
        cart_items=cart_items,
        cart_total=cart_total
    )

@app.route("/update-cart/<int:item_id>", methods=["POST"])
def update_cart(item_id):
    cart = session.get("cart", {})

    action = request.form.get("action")
    item_id = str(item_id)

    if item_id in cart:
        if action == "increase":
            cart[item_id] += 1

        elif action == "decrease":
            cart[item_id] -= 1

            if cart[item_id] <= 0:
                del cart[item_id]

        elif action == "remove":
            del cart[item_id]

    session["cart"] = cart

    return redirect("/cart")


@app.route("/checkout")
def checkout():
    cart = session.get("cart", {})

    if not cart:
        return redirect("/cart")

    cart_items = []
    cart_total = 0

    for item_id, quantity in cart.items():
        item = db.session.get(FoodItem, int(item_id))

        if item:
            item_total = item.price * quantity

            cart_items.append({
                "item": item,
                "quantity": quantity,
                "total": item_total
            })

            cart_total += item_total

    return render_template(
        "checkout.html",
        cart_items=cart_items,
        cart_total=cart_total
    )


@app.route("/place-order", methods=["POST"])
def place_order():
    name = request.form.get("name")
    phone = request.form.get("phone")
    address = request.form.get("address")

    cart = session.get("cart", {})

    if not cart:
        return redirect("/cart")

    cart_items = []
    order_total = 0

    for item_id, quantity in cart.items():
        item = db.session.get(FoodItem, int(item_id))

        if item:
            item_total = item.price * quantity

            cart_items.append({
                "item": item,
                "quantity": quantity,
                "total": item_total
            })

            order_total += item_total

    new_order = Order(
        name=name,
        phone=phone,
        address=address,
        total=order_total
    )

    db.session.add(new_order)
    db.session.commit()

    for item_id, quantity in cart.items():
        item = db.session.get(FoodItem, int(item_id))

        if item:
            order_item = OrderItem(
                order_id=new_order.id,
                food_item_id=item.id,
                quantity=quantity,
                price=item.price
            )

            db.session.add(order_item)

    db.session.commit()

    session["cart"] = {}

    return render_template(
        "order_success.html",
        name=name,
        phone=phone,
        address=address,
        cart_items=cart_items,
        order_total=order_total
    )


@app.route("/orders")
def orders():
    orders = Order.query.order_by(Order.id.desc()).all()
    return render_template("orders.html", orders=orders)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "admin123":
            session["admin_logged_in"] = True
            return redirect("/admin/orders")

        return "Invalid username or password"

    return render_template("admin_login.html")


@app.route("/admin/orders")
def admin_orders():
    if not session.get("admin_logged_in"):
        return redirect("/admin/login")

    orders = Order.query.order_by(Order.id.desc()).all()
    return render_template("admin_orders.html", orders=orders)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect("/admin/login")

@app.route("/cancel-order/<int:order_id>", methods=["POST"])
def cancel_order(order_id):
    order = db.session.get(Order, order_id)

    if not order:
        return redirect("/orders")

    if order.status == "Pending":
        order.status = "Cancelled"
        db.session.commit()

    return redirect("/orders")

@app.route("/admin/update-status/<int:order_id>", methods=["POST"])
def update_order_status(order_id):
    order = db.session.get(Order, order_id)

    if not order:
        return redirect("/admin/orders")

    status = request.form.get("status")

    if order.status == "Cancelled":
        return redirect("/admin/orders")

    if status in ["Pending", "Preparing", "Delivered"]:
        order.status = status
        db.session.commit()

    return redirect("/admin/orders")


with app.app_context():
    db.create_all()

    if FoodItem.query.count() == 0:
        food_items = [
            FoodItem(
                name="Classic Burger",
                category="Burgers",
                description="Juicy classic burger with fresh vegetables",
                price=149
            ),
            FoodItem(
                name="French Fries",
                category="Sides",
                description="Crispy golden french fries",
                price=99
            ),
            FoodItem(
                name="Margherita Pizza",
                category="Pizza",
                description="Classic pizza with tomato and mozzarella",
                price=249
            ),
            FoodItem(
                name="Veg Sandwich",
                category="Sandwiches",
                description="Fresh vegetable sandwich",
                price=129
            ),
            FoodItem(
                name="Cold Coffee",
                category="Drinks",
                description="Chilled creamy cold coffee",
                price=119
            )
        ]

        db.session.add_all(food_items)
        db.session.commit()


if __name__ == "__main__":
    app.run(debug=True)