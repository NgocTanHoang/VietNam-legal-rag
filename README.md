# Vietnamese Legal RAG System

A Retrieval-Augmented Generation (RAG) system designed for Vietnamese legal documents. This project leverages advanced AI and vector databases to provide accurate and context-aware responses to legal queries.

## Features

- **Document Ingestion**: Supports PDF and Parquet file formats for legal documents.
- **Vector Search**: Uses Qdrant for efficient similarity search.
- **Graph Database**: Integrates Neo4j for structured legal knowledge representation.
- **AI Agents**: Powered by LangChain and Grok for intelligent query processing.
- **API Integration**: Includes Lark webhook endpoints for seamless integration.
- **Modular Architecture**: Clean separation of concerns with agents, services, and data pipelines.

## Project Structure

- `app/`: Main application code
  - `agents/`: AI agents for legal processing
  - `api/`: API endpoints and integrations
  - `core/`: Configuration and settings
- `data_pipeline/`: Data ingestion and processing
- `models/`: Data models
- `services/`: Core services (retrieval, graph, etc.)
- `infra/`: Docker and infrastructure setup
- `notebook/`: Jupyter notebooks for experiments

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/NgocTanHoang/VietNam-legal-rag.git
   cd VietNam-legal-rag
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables in `app/core/config.py` or via environment variables.

4. Run with Docker:
   ```bash
   docker-compose up -d
   ```

## Usage

- Start the main application: `python app/main.py`
- Access API endpoints via the configured port.
- Use the notebook for experiments: `jupyter notebook notebook/experiments.ipynb`

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

## License

This project is licensed under the MIT License.