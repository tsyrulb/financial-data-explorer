# Public Financial Data Relationship Explorer

A web application for exploring relationships and correlations between publicly available financial and economic time series data. This project is currently under development.

## Features

* **Browse Datasets**: View a curated list of public financial and economic time series.
* **Multi-Select**: Choose multiple datasets for comparison and visualization.
* **Interactive Charting**: Plot selected series on an interactive line chart over a shared timeline.

### Planned Features

* Apply data transformations (e.g., index series to 100).
* Calculate and visualize rolling correlations between two series.
* Add event markers to align significant dates with data movements.

## Tech Stack

### Backend

* **Python 3.x** with [Flask](https://pypi.org/project/Flask/) 3.1.0
* [SQLAlchemy](https://www.sqlalchemy.org/) for database ORM
* [Pandas](https://pandas.pydata.org/) for data processing
* **SQLite** as a lightweight file-based database

### Frontend

* **React** with **TypeScript**
* **MUI (Material UI)** for UI components
* **MUI X Charts** for data visualization
* **Vite** as the frontend build tool

## Setup

### Prerequisites

* Python 3.x (with `pip`)
* Node.js (with `npm` or `yarn`)

### Clone the Repository

```bash
git clone <your-repo-url>
cd financial-data-explorer
```

### Backend Setup

1. Navigate to the backend folder:

   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   # Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   # Windows (CMD):
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```
4. Add your public data CSVs to `src/data/public_datasets/`. Ensure each file has:

   * An `observation_date` column
   * A single value column named after the series ticker
5. Initialize the database and load data:

   ```bash
   python src/setup_database.py
   ```

### Frontend Setup

1. From the project root, go to the frontend directory:

   ```bash
   cd frontend
   ```
2. Install dependencies:

   ```bash
   npm install
   # or
   yarn install
   ```

## Running the Application

### Start the Backend Server

1. Open a terminal in `backend` and activate the virtual environment.
2. Set the `FLASK_APP` environment variable:

   ```bash
   # Windows (PowerShell):
   $env:FLASK_APP = "src.app"
   # Windows (CMD):
   set FLASK_APP=src.app
   # macOS/Linux:
   export FLASK_APP=src.app
   ```
3. Launch the Flask server:

   ```bash
   flask run
   ```

### Start the Frontend Dev Server

1. In a new terminal, navigate to `frontend`.
2. Run:

   ```bash
   npm run dev
   # or
   yarn dev
   ```

### Access the App

Open your browser and visit the URL provided by Vite (typically `http://127.0.0.1:5173/`).

## Future Enhancements

* Integrate additional public data sources.
* Implement user accounts to save custom dashboards.
* Offer more transformation options (e.g., percentage change, log scale).
* Build rolling correlation analytics and UI.
* Add interactive event marker controls.
* Enhance chart features (zoom, pan, tooltips).
* Expand test coverage with unit and integration tests.
* Set up CI/CD pipelines for automated deployment.

---
