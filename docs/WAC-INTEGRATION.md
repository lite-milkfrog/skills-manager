# WebGPT-as-Codex integration

Skills Manager is an independent project. WAC integrates with it as an external local MCP component.

Stable contract:

- component id: `skills-control-plane`
- display name: Skills Manager
- MCP endpoint: `http://127.0.0.1:8943/mcp`
- manager endpoint: `http://127.0.0.1:8955/`
- gateway exposure: `gateway`
- dependency: `mcpjungle`

The human Manager UI is not in the Agent execution path. WAC and the browser UI are two consumers of the same local Skills Manager backend.

The standalone repository owns Skills Manager source and Workflow specs. The WAC repository owns the component declaration and integration contract.
