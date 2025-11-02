# UAF CGPA Calculator - M Saqlain

The \#1 automatic CGPA calculator designed for students of the **University of Agriculture Faisalabad (UAF)**. This tool provides a seamless, accurate, and feature-rich experience for calculating and managing academic results.

**Developed by Muhammad Saqlain (UAF Alumnus, BS Chemistry 2020-2024).**

### ✨ **Live Website: [uafcgpacalculator.vercel.app](https://uafcgpacalculator.vercel.app/)** ✨

## 🚀 Key Features

This calculator is built to be the most comprehensive and user-friendly tool for UAF students.

  * **🤖 Automatic Fetching**: Enter your registration number to automatically fetch your complete results from both the **UAF LMS** and the **UAF Attendance System**.
  * **🎯 100% Accurate Calculations**: Implements the official UAF grading formula and quality point table.
  * **🔄 Repeated Course Handling**: Automatically detects repeated courses and includes **only the best attempt** in the final CGPA calculation.
  * **🔮 CGPA Forecasting**: Add "Forecast Semesters" to plan your future grades and see your potential CGPA.
  * **✏️ Edit & Customize**:
      * Add custom courses and grades.
      * Delete or restore any course or semester.
      * Drag-and-drop courses between semesters (desktop).
  * **📄 Premium PDF Export**: Download a clean, professional, and well-formatted unofficial transcript of your results with a single click.
  * **💾 Profile Management**:
      * Save multiple profiles locally in your browser (e.g., for yourself, friends, or forecasts).
      * Import and Export your profiles as a JSON file for backup and restoration.
  * **📊 Detailed Analysis**: View a semester-wise breakdown with GPA, percentage, and a visual GPA trend chart.
  * **🌓 Modern UI**: A clean, responsive, and mobile-first interface with a beautiful **Dark Mode**.

## 🛠️ How It Works

The application simplifies the complex process of CGPA calculation into three simple steps:

1.  **Enter Registration Number**: The user provides their UAF registration number (e.g., `2020-ag-1234`).
2.  **Fetch Results**: The backend serverless function scrapes the UAF LMS and Attendance System portals, parsing the HTML to extract all course data.
3.  **Calculate & Display**: The frontend processes the data, applies the UAF grading logic (including handling repeated courses), and displays the final CGPA, percentage, and semester-wise results.

## 💻 Tech Stack

This project is a modern web application built with a separate frontend and a serverless backend.

  * **Frontend**:

      * **HTML5**
      * **CSS3** (with Bootstrap 5)
      * **JavaScript (Vanilla)**
      * **Chart.js**: For rendering the GPA trend graph.
      * **jsPDF & jsPDF-AutoTable**: For generating premium PDF reports.

  * **Backend (Serverless Function on Vercel)**:

      * **Python**: The core scraping and parsing logic.
      * **requests**: For making HTTP calls to the UAF portals.
      * **BeautifulSoup4**: For parsing the HTML responses from the servers.

  * **Deployment**:

      * **Vercel**: For hosting the frontend and the serverless Python backend.

## 👨‍💻 About the Developer

This calculator was built with care by **Muhammad Saqlain**, a proud alumnus of the University of Agriculture Faisalabad (BS Chemistry, 2020-2024). It was created to solve the common frustrations UAF students face in accurately calculating their academic standing.

**Connect with me:**

  * **LinkedIn**: [in/muhammad-saqlain-akbar](https://www.linkedin.com/in/muhammad-saqlain-akbar/)
  * **Facebook**: [UAFChemist.Rustam](https://www.facebook.com/UAFChemist.Rustam)
  * **Twitter (X)**: [@M\_Saqlain\_Akbar](https://x.com/M_Saqlain_Akbar)

## ⚠️ Disclaimer

This is an **unofficial, third-party tool**. It is not affiliated with, endorsed, or supported by the University of Agriculture Faisalabad (UAF). The calculations are based on the official grading formula but should be used for estimation purposes only.

**Always verify your official results with the university.**

