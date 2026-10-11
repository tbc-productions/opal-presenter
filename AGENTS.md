# UI guidance for agents

Before adding or changing operator dialogs, read
[the dialog design pattern](documentation/dialogs.md). The shared implementations
are in `opal/core/widgets/fluent_dialogs.py`, exported through
`opal.core.widgets.fluent`.

- Use the shared `ContentDialog` for compact prompts and confirmations, or
  `FormDialog` for forms with existing button-box validation. Larger editors,
  settings, browsers and wizards retain their specialised surfaces.
- Keep primary actions left, secondary actions in the middle and Cancel/Close
  right. Changing the default action must never reorder them.
- Keep validation and field updates before acceptance. Help and cancelled
  confirmations must leave the form open.
- Verify changed dialogs visually and run the relevant regression tests. Check
  long text, narrow hosts and keyboard submission as well as mouse clicks.
- Use Australian English in documentation, commits and pull requests.

# Naming

- Use Opal for all new internal names, including environment variables,
  identifiers and namespaces. Do not introduce new OpenLP names.
