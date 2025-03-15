# Career Coach - AI-Powered Resume and Career Document Analyzer

## Overview

Career Coach is a Streamlit-based web application that helps users analyze resumes, cover letters, and other career documents using Anthropic's Claude AI. The application provides detailed insights, feedback, and recommendations to improve career documents and enhance job search success.

## Features

- **Multiple Document Support**: Upload PDF, DOCX, and TXT files directly or process them from a specified folder
- **Comprehensive Analysis**: Get detailed feedback on your career documents
- **Multi-perspective Analysis**: View your documents from different angles including:
  - Main Analysis (customizable based on your query)
  - Strengths & Skills Identification
  - Improvement Areas
  - ATS Optimization Recommendations
- **Export Capabilities**: Save analysis results as text files for future reference
- **Streaming Responses**: See analysis results in real-time as they're generated

## Installation

### Prerequisites

- Python 3.7 or higher
- An API key from Anthropic (for Claude AI access)

### Setup

1. Clone this repository:

   ```
   git clone https://github.com/yourusername/career-coach.git
   cd career-coach
   ```

2. Install the required dependencies:

   ```
   pip install streamlit python-docx pypdf2 requests python-dotenv
   ```

3. Create a `.env` file in the project root directory with your Claude API key:

   ```
   CLAUDE_API_KEY=your_claude_api_key_here
   ```

## Usage

1. Start the application:

   ```
   streamlit run app.py
   ```

2. The application will open in your default web browser (typically at `http://localhost:8501`)

3. Upload your documents:

   - Use the "Upload Files" tab to directly upload documents from your device
   - Use the "Process Folder" tab to analyze documents from a specific directory

4. Customize your analysis:

   - Enter specific questions or areas of interest in the text area
   - Configure whether to generate summaries and export options

5. Click "Analyze" to process your documents

6. View the results in the tabbed interface:

   - Main Analysis (based on your query)
   - Strengths & Skills
   - Improvement Areas
   - ATS Optimization

## Setting Up Your Document Directory

If using the folder processing feature:

1. Create a directory for your career documents (default is `./documents`)
2. Place your PDF, DOCX, or TXT files in this directory
3. Enter the path in the application's "Folder path" field
4. Click "Scan Folder" to detect documents

## Exporting Results

1. Check "Export summaries to text files" 
2. Specify an export directory (default is `./summaries`)
3. The application will create this directory if it doesn't exist
4. Analysis results will be saved as text files named after the original documents

## Security Note

Your API key is stored locally in the `.env` file and is only used to communicate with Anthropic's Claude API. Your documents and their contents are processed locally before being sent to the API for analysis.

## Limitations

- Document text is limited to the first 2000 characters due to API constraints
- Processing large or numerous documents may take time depending on your internet connection
- The application requires an active internet connection to use the Claude API

## Troubleshooting

- **API Key Not Found**: Ensure your `.env` file is in the correct location and contains the proper key
- **File Not Reading Correctly**: Some PDFs with complex formatting or scanned documents may not extract text properly
- **API Request Errors**: Check your internet connection and Claude API status

## License

[MIT License](LICENSE)

## Acknowledgements

- Anthropic for providing the Claude AI API
- Streamlit for the web application framework
- PyPDF2 and python-docx for document parsing capabilities