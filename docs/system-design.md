# Medical Equipment ERP (V1)

## Technical Design Document

**Version:** 1.0

**Goal:** Build a lightweight web-based ERP for medical equipment distributors that manages inventory, sales, procurement, customers, and accounting through ERPNext.

---

# 1. Design Philosophy

## Objectives

The system should:

* Be easy to learn.
* Be deployable on a single VPS.
* Require minimal DevOps.
* Use ERPNext only for accounting and financial reporting.
* Provide a clean, modern UI designed for medical equipment suppliers.

This is **not** a generic ERP.

This is a **medical distribution management platform**.

---

# 2. System Architecture

```text
Users

↓

Next.js Frontend

↓

FastAPI Backend

↓

ERPNext REST API

↓

MariaDB
```

All components run using Docker Compose on a single server.

---

# 3. Technology Stack

## Frontend

* Next.js
* React
* TypeScript
* Material UI
* React Query

## Backend

* FastAPI
* SQLAlchemy
* Pydantic

## ERP

* ERPNext
* Frappe Framework

## Database

* MariaDB (managed by ERPNext)

## Reverse Proxy

* Nginx

## Background Services

* Redis (required by ERPNext)

## Deployment

* Docker Compose

---

# 4. Repository Structure

```text
medical-erp/

├── frontend/
│
├── backend/
│
├── nginx/
│
├── docker-compose.yml
│
├── docs/
│
└── scripts/
```

Backend

```text
backend/

api/

models/

schemas/

services/

integrations/

erpnext.py

utils/

config.py

main.py
```

---

# 5. User Roles

Administrator

Can access everything.

Manager

Can approve purchases.

Sales

Can create quotations, invoices and customers.

Store Keeper

Can receive stock.

Can transfer stock.

Can adjust stock.

Accountant

Can view financial reports.

Biomedical Engineer

Can manage installations and maintenance.

---

# 6. Core Modules

## Dashboard

Display

* Today's Sales
* Outstanding Receivables
* Outstanding Payables
* Low Stock
* Expiring Products
* Pending Deliveries
* Upcoming Maintenance

---

## Customers

Fields

* Name
* Address
* Phone
* Email
* Contact Person
* Customer Type
* Outstanding Balance

Actions

* Create
* Edit
* Delete
* View Purchase History

---

## Suppliers

Fields

* Name
* Contact
* Address
* Lead Time

Actions

* Create
* Purchase History
* Outstanding Payables

---

## Products

Fields

* Product Name
* SKU
* Barcode
* Category
* Manufacturer
* Purchase Price
* Selling Price
* Unit
* Image

Actions

* Create
* Edit
* Disable

---

## Inventory

Features

* Warehouses
* Stock Levels
* Batch Numbers
* Expiry Dates
* Goods Received
* Goods Issued
* Stock Adjustment
* Stock Transfer

Reports

* Current Stock
* Low Stock
* Expired Products
* Near Expiry

---

## Procurement

Workflow

Purchase Request

↓

Purchase Order

↓

Goods Received

↓

Supplier Invoice

↓

Payment

---

## Sales

Workflow

Quotation

↓

Sales Order

↓

Delivery

↓

Invoice

↓

Payment

---

## Equipment

Track

* Serial Number
* Customer
* Installation Date
* Warranty
* Status

---

## Maintenance

Track

* Service Ticket
* Assigned Engineer
* Visit Date
* Parts Used
* Customer Signature

---

## Finance

Finance is handled by ERPNext.

Expose

* Receivables
* Payables
* Cash Book
* Bank Book
* Income Statement
* Balance Sheet

through the backend.

---

# 7. API Design

Authentication

```
POST /login

POST /logout
```

Customers

```
GET /customers

POST /customers

PUT /customers/{id}

DELETE /customers/{id}
```

Products

```
GET /products

POST /products

PUT /products/{id}
```

Inventory

```
GET /inventory

POST /inventory/receive

POST /inventory/issue

POST /inventory/transfer
```

Sales

```
POST /quotation

POST /sales-order

POST /invoice
```

Purchasing

```
POST /purchase-order

POST /goods-received
```

Equipment

```
POST /equipment

GET /equipment

POST /equipment/install
```

Maintenance

```
POST /ticket

PUT /ticket/{id}

POST /maintenance
```

Reports

```
GET /reports/profit-loss

GET /reports/balance-sheet

GET /reports/stock
```

---

# 8. ERP Integration

The frontend **must never communicate directly with ERPNext**.

Flow

```
Frontend

↓

FastAPI

↓

ERPNext API

↓

ERPNext
```

Create Invoice

↓

FastAPI validates request

↓

Calls ERPNext Sales Invoice API

↓

Returns success to frontend

---

# 9. Dashboard

Cards

* Today's Revenue
* Inventory Value
* Outstanding Customers
* Outstanding Suppliers
* Low Stock
* Products Expiring Soon
* Pending Maintenance

Recent Activity

* Latest Sales
* Latest Purchases
* Recent Payments

---

# 10. File Uploads

Support

* Product Images
* Equipment Photos
* Warranty Documents
* User Manuals
* Installation Reports

Store locally on the server for V1.

---

# 11. Security

* JWT Authentication
* Password Hashing
* Role-Based Access Control
* HTTPS
* Audit log for important actions

---

# 12. Deployment

One Ubuntu VPS

Run

* Nginx
* Next.js
* FastAPI
* ERPNext
* MariaDB
* Redis

using Docker Compose.

Nightly automated database backups.

---

# 13. Future Features (Not in V1)

* AI Assistant
* WhatsApp Notifications
* Barcode Scanning
* Offline Mode (PWA)
* Mobile Application
* Subscription Billing
* Multi-Tenant SaaS
* Predictive Stock Forecasting
* Preventive Maintenance Scheduling
* Customer Portal

---

# 14. Definition of Done

The system is considered complete when a medical equipment supplier can:

* Manage customers and suppliers.
* Maintain a product catalog.
* Receive inventory into stock.
* Track batches and expiry dates.
* Create quotations and invoices.
* Record purchases.
* Manage serialised equipment.
* Record maintenance activities.
* View receivables and payables.
* Generate an Income Statement and Balance Sheet through ERPNext.
* Deploy the complete system on a single VPS using Docker Compose.

