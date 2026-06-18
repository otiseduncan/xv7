# X Kernel Browser Panel

This document records the first browser-facing X Kernel control panel.

## URL

When the local Docker stack is running, open:

```text
http://localhost:5173/x-kernel.html
```

The page is served by the existing XV7 frontend container.

## Auth path

The browser panel calls the API through the existing frontend proxy:

```text
/api/* -> xv7-core:8000
```

The frontend nginx config injects `X-XV7-API-Key`, so the operator does not paste API keys into the browser.

## Supported browser actions

The panel can:

- create a session
- send a request through `/sessions/{session_id}/messages`
- show the assistant/kernel response
- detect the latest staged action ID
- review latest stage
- preview stage
- validate approval intent
- prepare package draft
- review latest package draft
- attach operator-reviewed content to a draft
- cancel a stage

## Safety state

The panel does not add apply/write execution. It only surfaces the already-proven backend authority chain.

Current safe chain:

```text
stage
-> review
-> preview
-> validate approval intent
-> prepare draft package
-> review draft package
-> attach operator content
```

Still blocked:

```text
repo write
shell execution
executor pending queue promotion
automatic apply
system/network control
```

Package drafts remain under:

```text
data/x_inbox/drafts
```

They are not moved into:

```text
data/x_inbox/pending
```

That means the existing prompt executor cannot accidentally apply a draft just because it exists.
