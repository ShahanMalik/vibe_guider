# Vibe Guider

Vibe Guider is an AI-powered software project advisor that turns a user's idea or technical question into structured guidance. It uses a multi-agent workflow to understand requirements, recommend tools, design an architecture, identify risks, gather useful resources, and compose a final answer.

> [!WARNING]
> **This project is still under development and is not complete.**
>
> Several features, tests, security controls, deployment configurations, and user-facing components still need to be completed. The current version should be treated as an experimental prototype, not a production-ready application.

## Current Capabilities

- Understands a project idea or technical request.
- Generates smart clarification questions when more information is needed.
- Recommends tools, frameworks, packages, and technologies.
- Produces software architecture guidance.
- Reviews technical risks and possible implementation problems.
- Collects relevant external resources.
- Combines agent outputs into one structured final response.
- Supports normal and streamed API responses.
- Generates a downloadable ZIP bundle from an AI-produced project structure.
- Allows the OpenAI model to be configured through an environment variable.

## How It Works

Vibe Guider uses a LangGraph-based multi-agent workflow:

```text
User Request
    |
    v
Requirement Agent
    |
    +---- More information needed ----> Smart Clarification Questions
    |
    v
Tool Agent
    |
    v
Architecture Agent
    |
    v
Risk Agent
    |
    v
Resource Agent
    |
    v
Supervisor
    |
    v
Final Answer
```

For recommendation and comparison requests, the workflow can skip the architecture stage and continue directly to risk analysis.

## Technology Stack

- Python
- FastAPI
- Uvicorn
- OpenAI API
- LangGraph
- LangChain Core
- Pydantic
- FastMCP
- Python Dotenv
- Tenacity
- DDGS

## Project Structure

```text
vibe_guider/
├── backend/
│   ├── agents/              # Specialized AI agents and LLM integration
│   ├── graph/               # LangGraph state and workflow definition
│   ├── knowledge/           # Agent instructions and knowledge content
│   ├── mcp_servers/         # MCP-related server components
│   ├── app.py               # FastAPI application and API endpoints
│   └── requirements.txt     # Python dependencies
└── README.md
```

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/ShahanMalik/vibe_guider.git
cd vibe_guider/backend
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

Activate it on Windows:

```powershell
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file inside the `backend` directory:

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini-2024-07-18
```

`OPENAI_API_KEY` is required. `OPENAI_MODEL` is optional and uses the model configured in the code when omitted.

> [!IMPORTANT]
> Never commit your `.env` file or API key to GitHub. OpenAI API usage may create charges on your OpenAI account.

### 5. Start the API

Run this command from the `backend` directory:

```bash
uvicorn app:app --reload
```

The API will normally be available at:

```text
http://127.0.0.1:8000
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

## API Endpoints

### Health Check

```http
GET /
```

Example response:

```json
{
  "status": "running"
}
```

### Ask Vibe Guider

```http
POST /ask
Content-Type: application/json
```

Example request:

```json
{
  "question": "Design the architecture for a Flutter e-commerce application",
  "project_type": "mobile_app",
  "request_mode": "architecture_guide"
}
```

The endpoint may return clarification questions first. Send the user's selected choices in a later request through fields such as `smart_questions`, `user_choices`, `auto_decisions`, and `project_summary`.

### Stream a Response

```http
POST /ask/stream
Content-Type: application/json
```

This endpoint returns newline-delimited JSON (`application/x-ndjson`) containing workflow stages, text chunks, clarification choices, completion data, or errors.

### Download a Generated Project Bundle

```http
POST /download/zip
Content-Type: application/json
```

Example request:

```json
{
  "title": "flutter-shop",
  "content": "# Project Structure\n\n```text\nflutter-shop/\n├── lib/\n└── README.md\n```"
}
```

The response is a ZIP archive containing the parsed project structure, generated guide content, and a `vibe-guider-manifest.json` file.

## Example cURL Request

```bash
curl -X POST "http://127.0.0.1:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Recommend a backend architecture for a food delivery app"
  }'
```

## Important Current Limitations

The following items are incomplete or require improvement:

- No complete production frontend is documented in the current repository.
- No authentication or user-management system is implemented.
- No API rate limiting or usage quotas are implemented.
- CORS currently allows all origins and must be restricted before deployment.
- Automated unit, integration, and end-to-end tests are not yet included.
- Error handling and structured logging need improvement.
- API request validation and generated-content validation need further hardening.
- The streaming endpoint uses an in-process worker thread and queue; scalability has not been validated.
- Generated architecture and tool recommendations may contain AI mistakes and must be reviewed by a developer.
- External-resource results may be incomplete, outdated, or unavailable.
- No database or persistent conversation history is currently documented.
- No Docker, CI/CD, monitoring, or production deployment configuration is included.
- Performance, concurrency, security, and cost behavior have not been fully tested.
- Dependency versions are not pinned, which may cause future compatibility problems.
- A software license has not yet been added to the repository.

## Security Notes

Before using this project in production:

1. Restrict allowed CORS origins.
2. Add authentication and authorization.
3. Add request-size limits, rate limiting, and abuse protection.
4. Store secrets in a secure secret manager rather than source code.
5. Validate all generated filenames, paths, and downloadable content.
6. Add dependency and vulnerability scanning.
7. Avoid returning internal exception details to clients.
8. Add audit logs without recording API keys or sensitive user data.
9. Review AI output before executing generated commands or code.

## Roadmap

- [ ] Complete the user interface.
- [ ] Add authentication and user accounts.
- [ ] Save projects and conversation history.
- [ ] Add reusable project templates.
- [ ] Add unit and integration tests.
- [ ] Pin and regularly update dependency versions.
- [ ] Add Docker support.
- [ ] Add CI/CD workflows.
- [ ] Add structured logging and monitoring.
- [ ] Improve streaming reliability and cancellation.
- [ ] Add rate limiting and cost controls.
- [ ] Add production-ready security configuration.
- [ ] Improve generated ZIP project files and templates.
- [ ] Add deployment documentation.
- [ ] Add a license.

## Contributing

The project is still evolving, so contributions, bug reports, and improvement ideas are welcome. Before making a large change, open an issue describing the proposed work.

Suggested contribution process:

```bash
git checkout -b feature/your-feature
git commit -m "Add your feature"
git push origin feature/your-feature
```

Then open a pull request against the `main` branch.

## Disclaimer

Vibe Guider uses a large language model to generate technical guidance. Its responses may be incomplete or incorrect. Always review architecture decisions, packages, commands, security recommendations, and generated code before using them in a real project.

## Author

Developed by [Shahan Malik](https://github.com/ShahanMalik).
