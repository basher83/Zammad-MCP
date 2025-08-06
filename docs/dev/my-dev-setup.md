# My Development Setup

## Codespaces

### Tailscale

It is installed via:

```bash
go install tailscale.com/cmd/tailscale@latest tailscale.com/cmd/tailscaled@latest
```

To run Tailscale, use the following command:

```bash
sudo tailscaled --state=/var/lib/tailscale/tailscaled.state --socket=/var/run/tailscale/tailscaled.sock &
```

Log in to Tailscale with:

```bash
sudo tailscale up --authkey <your-auth-key>
```

OR for web login:

```bash
sudo tailscale up
```
