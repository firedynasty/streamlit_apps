# Career Coach - Resume Analyzer

A Streamlit application for analyzing resumes, cover letters, and other career documents using local AI models via Ollama.

Note: I have different versions, 1,2,3,4,5, 5 should work

## Features

- **Document Analysis**: Upload PDF, DOCX, or TXT files for AI-powered analysis
- **Folder Processing**: Scan a folder to process multiple documents at once
- **Multi-faceted Analysis**: Get insights on:
  - Overall document quality
  - Key strengths and skills
  - Areas for improvement
  - ATS (Applicant Tracking System) optimization
- **Export Capabilities**: Save analysis results to text files

## Requirements

- Python 3.7+
- Streamlit
- PyPDF2
- python-docx
- requests
- Ollama (running locally)

## Installation

1. Clone this repository or download the source code
   ```bash
   git clone <repository-url>
   cd career-coach
   ```

2. Install the required Python packages
   ```bash
   pip install streamlit PyPDF2 python-docx requests
   ```

3. Install Ollama following instructions at [ollama.ai](https://ollama.ai)

4. Pull a suitable LLM model with Ollama
   ```bash
   ollama pull deepseek-r1:1.5b  # or another model of your choice
   ```

## Configuration

Edit the `CareerCoach` class constructor in the main script to specify your preferred model:

```python
def __init__(self):
    self.api_base = 'http://localhost:11434/api'
    self.model = 'deepseek-r1:1.5b'  # Change to any model installed in Ollama
```

## Usage

1. Start the Ollama service:
   ```bash
   ollama serve
   ```

2. Run the Streamlit app:
   ```bash
   streamlit run career_coach.py
   ```

3. Open your web browser to view the app (typically at http://localhost:8501)

4. Upload documents or specify a folder to scan

5. Set your analysis options and click "Analyze"

## Document Folder Structure

If using the folder processing option, organize your documents as follows:

```
documents/
├── resume1.pdf
├── resume2.docx
├── coverletter.txt
└── ...
```

## Exporting Results

Enable the "Export summaries to text files" option to save analysis results. By default, they will be saved to the `./summaries` directory.

## Troubleshooting

- **Port in use error**: If Ollama reports that port 11434 is already in use, it means Ollama is already running or another service is using that port. Try:
  ```bash
  pkill ollama  # Kill any running Ollama processes
  ollama serve  # Then restart
  ```

- **Model not found error**: Make sure you have pulled the model specified in the script:
  ```bash
  ollama list        # Check available models
  ollama pull <model>  # Pull required model
  ```

- **Slow or incomplete responses**: Ollama performance depends on your hardware. For better results:
  - Try a smaller model if your computer has limited resources
  - Ensure your system has adequate RAM
  - Consider using quantized models for better performance on consumer hardware

## Customization

You can modify the prompts in the `analyze_content` method to customize the analysis for different purposes or industries.

## License

[Insert your license information here]

## Credits

This tool leverages:
- Ollama for local LLM inference
- Streamlit for the web interface
- PyPDF2 and python-docx for document parsing
