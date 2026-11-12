const KEY = "sd_farm_cart_v4";

// ==========================================
// 1. GET CART
// ==========================================

function get() {
    try {
        const data = JSON.parse(localStorage.getItem(KEY) || "{}");

        if (!data || typeof data !== "object" || Array.isArray(data)) {
            return {};
        }

        return Object.fromEntries(
            Object.entries(data).filter(([id, item]) =>
                /^\d+$/.test(id) &&
                item &&
                Number.isInteger(Number(item.qty)) &&
                Number(item.qty) > 0 &&
                Number.isFinite(Number(item.price)) &&
                Number(item.price) >= 0
            ).map(([id, item]) => [
                id,
                {
                    ...item,
                    qty: Number(item.qty),
                    price: Number(item.price)
                }
            ])
        );

    } catch (error) {
        console.error("Cart loading error:", error);
        return {};
    }
}


// ==========================================
// 2. SAVE CART
// ==========================================

function save(cart) {
    try {
        localStorage.setItem(KEY, JSON.stringify(cart));
    } catch (error) {
        console.error("Cart saving error:", error);
        alert("Unable to save cart. Please enable browser storage.");
        return;
    }

    updateCart();
}


// ==========================================
// 3. MONEY FORMAT
// ==========================================

function money(amount) {
    return "Rs. " + Math.round(amount).toLocaleString("en-IN");
}


// ==========================================
// 4. UPDATE CART COUNT
// ==========================================

function count() {
    const cart = get();

    const total = Object.values(cart).reduce(
        (sum, item) => sum + item.qty,
        0
    );

    document.querySelectorAll("#cart-count").forEach(element => {
        element.textContent = total;
    });
}


// ==========================================
// 5. UPDATE PRODUCT QUANTITY DISPLAY
// ==========================================

function updateProductQuantity(id) {
    const cart = get();

    const element = document.getElementById("qty-" + id);

    if (element) {
        element.textContent = cart[id]?.qty || 0;
    }
}


// ==========================================
// 6. ADD PRODUCT
// ==========================================

function add(button) {
    const id = String(button.dataset.id || "");

    if (!/^\d+$/.test(id)) {
        console.error("Invalid product ID:", id);
        return;
    }

    const cart = get();

    const price = Number(button.dataset.price);

    if (!Number.isFinite(price) || price < 0) {
        alert("Invalid product price.");
        return;
    }

    if (!cart[id]) {
        cart[id] = {
            id: id,
            name: button.dataset.name || "Product",
            price: price,
            unit: button.dataset.unit || "",
            qty: 0
        };
    }

    if (cart[id].qty >= 100) {
        alert("Maximum quantity is 100 per product.");
        return;
    }

    cart[id].qty++;

    save(cart);

    updateProductQuantity(id);
}


// ==========================================
// 7. CHANGE PRODUCT QUANTITY
// ==========================================

function change(id, amount) {
    const cart = get();

    if (!cart[id]) return;

    const newQuantity = cart[id].qty + amount;

    if (newQuantity > 100) {
        alert("Maximum quantity is 100.");
        return;
    }

    if (newQuantity <= 0) {
        delete cart[id];
    } else {
        cart[id].qty = newQuantity;
    }

    save(cart);

    updateProductQuantity(id);
}


// ==========================================
// 8. CART LINE CREATION
// ==========================================

function appendCartLine(container, item) {
    const line = document.createElement("div");

    line.className = "line";

    const name = document.createElement("span");

    name.textContent = `${item.name} × ${item.qty}`;

    const price = document.createElement("b");

    price.textContent = money(item.price * item.qty);

    line.append(name, price);

    container.appendChild(line);

    return item.price * item.qty;
}


// ==========================================
// 9. DISPLAY CART
// ==========================================

function render() {
    const container = document.querySelector("#cart-lines");

    if (!container) return;

    const cart = get();

    const items = Object.values(cart);

    container.replaceChildren();

    let subtotal = 0;

    if (items.length === 0) {
        const empty = document.createElement("p");

        empty.textContent = "Your cart is empty.";

        container.appendChild(empty);

    } else {
        items.forEach(item => {
            subtotal += appendCartLine(container, item);
        });
    }

    const subtotalElement = document.querySelector("#cart-subtotal");

    if (subtotalElement) {
        subtotalElement.textContent = money(subtotal);
    }
}


// ==========================================
// 10. CHECKOUT SUMMARY
// ==========================================

function checkout() {
    const container = document.querySelector("#checkout-lines");

    if (!container) return;

    const cart = get();

    const items = Object.values(cart);

    container.replaceChildren();

    let subtotal = 0;

    if (items.length === 0) {
        const empty = document.createElement("p");

        empty.textContent = "Your cart is empty.";

        container.appendChild(empty);

    } else {
        items.forEach(item => {
            subtotal += appendCartLine(container, item);
        });
    }

    const subtotalElement = document.querySelector("#checkout-subtotal");

    if (subtotalElement) {
        subtotalElement.textContent = money(subtotal);
    }

    // Delivery charge

    const area = document.querySelector("#area");

    let deliveryFee = 0;

    if (area && area.selectedOptions.length > 0) {
        deliveryFee = Number(
            area.selectedOptions[0].dataset.fee || 0
        );
    }

    const feeElement = document.querySelector("#delivery-fee");

    if (feeElement) {
        feeElement.textContent = money(deliveryFee);
    }

    // Final total

    const totalElement = document.querySelector("#checkout-total");

    if (totalElement) {
        totalElement.textContent = money(subtotal + deliveryFee);
    }

    // Hidden cart data for Flask

    const hiddenCart = document.querySelector("#cart-json");

    if (hiddenCart) {
        hiddenCart.value = JSON.stringify(
            Object.fromEntries(
                items.map(item => [item.id, item.qty])
            )
        );
    }
}


// ==========================================
// 11. UPDATE EVERYTHING
// ==========================================

function updateCart() {
    count();
    render();
    checkout();
}


// ==========================================
// 12. PAYMENT METHOD
// ==========================================

function updatePayment() {
    const panel = document.getElementById("payment-details");

    const qr = document.getElementById("payment-qr");

    const title = document.getElementById("payment-details-title");

    const selected = document.querySelector(
        'input[name="payment_method"]:checked'
    );

    if (!panel || !qr || !selected) return;

    const method = selected.value;

    if (method === "Cash on Delivery") {
        panel.hidden = true;
        return;
    }

    const qrSources = {
        "eSewa": qr.dataset.esewa,
        "Bank Transfer": qr.dataset.bank,
        "Khalti": qr.dataset.khalti
    };

    if (!qrSources[method]) return;

    panel.hidden = false;

    qr.src = qrSources[method];

    qr.alt = method + " payment QR code";

    if (title) {
        title.textContent = method + " Payment";
    }
}


// ==========================================
// 13. INITIALIZE WEBSITE
// ==========================================

document.addEventListener("DOMContentLoaded", function () {

    // Initial cart display

    updateCart();

    // Restore product quantities

    document.querySelectorAll(".add").forEach(button => {
        updateProductQuantity(String(button.dataset.id));
    });


    // PLUS BUTTON

    document.querySelectorAll(".plus").forEach(button => {

        button.addEventListener("click", function () {

            const id = String(this.dataset.id);

            const addButton = document.querySelector(
                `.add[data-id="${id}"]`
            );

            if (!addButton) {
                console.error("Add button not found for product:", id);
                return;
            }

            add(addButton);

        });

    });


    // MINUS BUTTON

    document.querySelectorAll(".minus").forEach(button => {

        button.addEventListener("click", function () {

            const id = String(this.dataset.id);

            change(id, -1);

        });

    });


    // ADD TO CART BUTTON

    document.querySelectorAll(".add").forEach(button => {

        button.addEventListener("click", function () {

            add(this);

        });

    });


    // MOBILE NAVIGATION

    document.querySelector(".hamb")?.addEventListener("click", function () {

        document.querySelector("nav")?.classList.toggle("open");

    });


    // PAYMENT METHOD CHANGE

    document.querySelectorAll(
        'input[name="payment_method"]'
    ).forEach(radio => {

        radio.addEventListener("change", updatePayment);

    });

    updatePayment();


    // DELIVERY AREA CHANGE

    document.querySelector("#area")?.addEventListener("change", checkout);


    // CHECKOUT FORM

    document.querySelector("#checkout-form")?.addEventListener(
        "submit",
        function (event) {

            const cart = get();

            if (Object.keys(cart).length === 0) {

                event.preventDefault();

                alert("Your cart is empty.");

                return;
            }

            checkout();

        }
    );

});
