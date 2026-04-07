import asyncio
import logging


async def run_deploy_commands(repo_name, repo_config):
    """Background task to run deployment commands asynchronously"""
    path = repo_config["path"]
    branch = repo_config["branch"]
    timeout = repo_config["timeout"]
    deploy_commands = repo_config.get("commands")

    try:
        logging.info(
            f"--- Starting async deployment for {repo_name} ({branch}) at {path} ---"
        )

        if not deploy_commands:
            logging.info(f"[{repo_name}] No deployment commands specified. Skipping.")
            return

        success = True
        for cmd in deploy_commands:
            logging.info(f"[{repo_name}] Executing: {cmd}")

            # Start the subprocess
            process = await asyncio.create_subprocess_shell(
                cmd,
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                # Wait for the command to finish with a timeout
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )

                if stdout:
                    logging.info(f"[{repo_name}] Output: {stdout.decode().strip()}")

                if process.returncode != 0:
                    logging.error(
                        f"[{repo_name}] Command failed with exit code {process.returncode}"
                    )
                    if stderr:
                        logging.error(f"[{repo_name}] Error: {stderr.decode().strip()}")
                    success = False
                    break

            except asyncio.TimeoutError:
                logging.error(
                    f"[{repo_name}] Command timed out after {timeout}s: {cmd}"
                )
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                success = False
                break

        if success:
            logging.info(f"--- [{repo_name}] Deployment finished successfully ---")
        else:
            logging.error(f"--- [{repo_name}] Deployment failed ---")

    except Exception as e:
        logging.error(
            f"[{repo_name}] Unexpected error during async deployment: {str(e)}"
        )
