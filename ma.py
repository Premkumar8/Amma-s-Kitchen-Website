from app import app, db, Product, ProductImage

with app.app_context():
    # Create products
    product1 = Product(name='Sambar Powder', mrp=150.00, price=120.00, stock=50)
    product2 = Product(name='Chettinad Snacks', mrp=100.00, price=80.00, stock=75)
    product3 = Product(name='Homemade Ghee', mrp=500.00, price=450.00, stock=30)
    product4 = Product(name='Biryani Masala', mrp=200.00, price=180.00, stock=60)
    product5 = Product(name='Rasam Powder', mrp=150.00, price=120.00, stock=45)
    
    # Add products to the database session
    db.session.add(product1)
    db.session.add(product2)
    db.session.add(product3)
    db.session.add(product4)
    db.session.add(product5)

    # Commit the changes to the database
    db.session.commit()

    # Create images for the products
    image1 = ProductImage(image_url='prod-sambar.svg', product=product1)
    image2 = ProductImage(image_url='prod-chettinad.svg', product=product2)
    image3 = ProductImage(image_url='prod-ghee.svg', product=product3)
    image4 = ProductImage(image_url='prod-biryani.svg', product=product4)
    image5 = ProductImage(image_url='prod-rasam.svg', product=product5)

    # Add images to the session
    db.session.add(image1)
    db.session.add(image2)
    db.session.add(image3)
    db.session.add(image4)
    db.session.add(image5)
    
    # Commit the image data
    db.session.commit()

    print("Products and product images added successfully!")