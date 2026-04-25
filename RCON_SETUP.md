# How to Enable RCON on Your Minecraft Server

RCON (Remote Console) must be enabled on your Minecraft server for the dashboard to connect.

## Step 1: Edit server.properties

On your Minecraft server (ubuntu-desktop), find the `server.properties` file in your Minecraft directory.

Add or update these lines:

```properties
# Enable RCON
enable-rcon=true

# RCON port (default is 25575 - you can change this if needed)
rcon.port=25575

# RCON password - CHANGE THIS to something secure!
rcon.password=your_secure_password_here
```

## Step 2: Restart Your Minecraft Server

After saving `server.properties`, restart the Minecraft server for changes to take effect.

## Step 3: Update Your Dashboard .env File

On your Windows machine where the dashboard runs, edit `.env` and add your RCON password:

```bash
MC_SERVER_HOST=ubuntu-desktop
MC_RCON_PORT=25575
MC_RCON_PASSWORD=your_secure_password_here  # Must match server.properties!
```

## Step 4: Test RCON Connection

You can test if RCON is working by trying to connect manually:

### From the server itself:
```bash
# Install mcrcon if needed
sudo apt install mcrcon

# Test connection
mcrcon -H localhost -P 25575 -p your_password "list"
```

### From your Windows machine:
```bash
# After installing dependencies
pip install mcrcon

# Test in Python
python -c "from mcrcon import MCRcon; print(MCRcon('ubuntu-desktop', 'your_password').connect().command('list'))"
```

## Security Notes

- **Firewall**: Make sure port 25575 is accessible from your dashboard machine (192.168.x.x network)
- **Password**: Use a strong RCON password - anyone with this can run commands on your server!
- **Network**: RCON traffic is NOT encrypted by default. Only use on trusted networks (LAN/VPN).

## Troubleshooting

**"Connection refused"**
- Check firewall allows port 25575
- Verify server.properties has `enable-rcon=true`
- Make sure you restarted the server after editing server.properties

**"Authentication failed"**
- Password in `.env` must exactly match `rcon.password` in server.properties
- No spaces or quotes needed in the password

**"Unknown host"**
- Replace `ubuntu-desktop` with the actual IP address if DNS doesn't resolve
- Try `192.168.1.x` (whatever IP your server has)
