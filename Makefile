.PHONY: all build-ui deploy-ui clean help

# Default target
all: build-ui deploy-ui

# Build the React UI
build-ui:
	@echo "Building React UI..."
	cd web_ui && npm run build
	@echo "UI build complete!"

# Deploy the built UI to the agent's client directory
deploy-ui:
	@echo "Deploying UI to agent/src/client/web_ui..."
	@rm -rf agent/src/client/web_ui
	@mkdir -p agent/src/client
	@cp -r web_ui/build agent/src/client/web_ui
	@echo "UI deployed successfully!"

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	@rm -rf web_ui/build
	@rm -rf agent/src/client/web_ui
	@echo "Clean complete!"

# Help target
help:
	@echo "Available targets:"
	@echo "  all        - Build and deploy the UI (default)"
	@echo "  build-ui   - Build the React UI"
	@echo "  deploy-ui  - Deploy built UI to agent/src/client/web_ui"
	@echo "  clean      - Remove build artifacts"
	@echo "  help       - Show this help message"

