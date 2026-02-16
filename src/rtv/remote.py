"""SSH/SFTP operations for remote Plex server file management."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from rtv.config import SSHConfig


def _get_client(ssh_config: SSHConfig):  # type: ignore[no-untyped-def]
    """Create and return a connected paramiko SSHClient."""
    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs: dict[str, object] = {
        "hostname": ssh_config.host,
        "port": ssh_config.port,
        "username": ssh_config.username,
    }
    if ssh_config.key_path:
        connect_kwargs["key_filename"] = ssh_config.key_path

    client.connect(**connect_kwargs)  # type: ignore[arg-type]
    return client


def test_connection(ssh_config: SSHConfig) -> bool:
    """Test SSH connectivity. Returns True on success."""
    try:
        client = _get_client(ssh_config)
        client.close()
        return True
    except Exception:
        return False


def list_remote_dir(ssh_config: SSHConfig, path: str) -> list[str]:
    """List files and directories at a remote path via SFTP."""
    client = _get_client(ssh_config)
    try:
        sftp = client.open_sftp()
        try:
            entries = sftp.listdir(path)
            return sorted(entries)
        finally:
            sftp.close()
    finally:
        client.close()


def upload_file(ssh_config: SSHConfig, local_path: Path, remote_path: str) -> None:
    """Upload a local file to the remote server via SFTP."""
    client = _get_client(ssh_config)
    try:
        sftp = client.open_sftp()
        try:
            # Ensure remote directory exists
            remote_dir = str(PurePosixPath(remote_path).parent)
            _mkdir_p(sftp, remote_dir)
            sftp.put(str(local_path), remote_path)
        finally:
            sftp.close()
    finally:
        client.close()


def download_file(ssh_config: SSHConfig, remote_path: str, local_path: Path) -> None:
    """Download a remote file to a local path via SFTP."""
    local_path.parent.mkdir(parents=True, exist_ok=True)
    client = _get_client(ssh_config)
    try:
        sftp = client.open_sftp()
        try:
            sftp.get(remote_path, str(local_path))
        finally:
            sftp.close()
    finally:
        client.close()


def run_remote_command(ssh_config: SSHConfig, command: str) -> tuple[str, str, int]:
    """Execute a command on the remote server.

    Returns (stdout, stderr, exit_code).
    """
    client = _get_client(ssh_config)
    try:
        _, stdout, stderr = client.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        return stdout.read().decode(), stderr.read().decode(), exit_code
    finally:
        client.close()


def scan_remote_commercials(ssh_config: SSHConfig, base_path: str) -> list[dict]:
    """Scan remote commercial directory structure.

    Returns list of dicts with: name, count (number of mp4 files).
    """
    client = _get_client(ssh_config)
    try:
        sftp = client.open_sftp()
        try:
            results = []
            try:
                entries = sftp.listdir(base_path)
            except FileNotFoundError:
                return []

            for entry in sorted(entries):
                entry_path = f"{base_path}/{entry}"
                try:
                    stat = sftp.stat(entry_path)
                    import stat as stat_module
                    if stat_module.S_ISDIR(stat.st_mode):  # type: ignore[arg-type]
                        # Count mp4 files in subdirectory
                        try:
                            files = sftp.listdir(entry_path)
                            mp4_count = sum(1 for f in files if f.lower().endswith(".mp4"))
                            if mp4_count > 0:
                                results.append({"name": entry, "count": mp4_count})
                        except Exception:
                            pass
                except Exception:
                    pass

            return results
        finally:
            sftp.close()
    finally:
        client.close()


def _mkdir_p(sftp: object, remote_dir: str) -> None:
    """Recursively create remote directories (like mkdir -p)."""
    if not remote_dir or remote_dir == "/":
        return
    try:
        sftp.stat(remote_dir)  # type: ignore[union-attr]
    except FileNotFoundError:
        parent = str(PurePosixPath(remote_dir).parent)
        _mkdir_p(sftp, parent)
        try:
            sftp.mkdir(remote_dir)  # type: ignore[union-attr]
        except OSError:
            pass  # Already exists (race condition)
