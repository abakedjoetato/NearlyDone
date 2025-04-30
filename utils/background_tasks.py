"""
Background Task Utility for Discord Commands

This module provides utilities to run long-running tasks in the background
while providing immediate feedback to users in Discord.

This prevents Discord interactions from timing out while still allowing
complex operations to complete.
"""

import asyncio
import logging
import discord
import functools
import traceback
from typing import Dict, Any, Callable, Coroutine, Optional, Union

logger = logging.getLogger('deadside_bot.utils.background_tasks')

# Global task registry to prevent garbage collection
active_tasks = {}


async def run_task_with_progress(
    ctx: discord.ApplicationContext,
    task_func: Callable[..., Coroutine],
    *args,
    initial_message: str = "⏳ Processing your request...",
    update_interval: int = 10,  # Update frequency in seconds
    timeout: int = 300,  # 5 minutes timeout by default
    **kwargs
) -> None:
    """
    Run a long task in the background with progress updates.
    
    Args:
        ctx: The Discord context
        task_func: The async function to run
        initial_message: The message to send immediately
        update_interval: How often to check for progress updates
        timeout: Max time in seconds for the task to run
        *args, **kwargs: Arguments to pass to task_func
    """
    # Create a task-specific progress store
    task_id = f"{ctx.guild.id}_{ctx.author.id}_{ctx.command.name}_{asyncio.get_event_loop().time()}"
    progress = {
        'status': 'starting',
        'message': initial_message,
        'percent': 0,
        'error': None,
        'result': None,
        'updates': [],
    }
    
    # Store in global registry
    active_tasks[task_id] = progress
    
    # Send initial response
    response = await ctx.respond(initial_message)
    msg = await response.original_response()
    
    async def update_progress_message():
        """Periodically update the progress message"""
        last_status = None
        
        try:
            start_time = asyncio.get_event_loop().time()
            while True:
                # Get current status
                current = active_tasks.get(task_id, {})
                status = current.get('status')
                
                # Exit conditions
                if status in ['completed', 'failed'] or asyncio.get_event_loop().time() - start_time > timeout:
                    break
                
                # Only update if changed
                if status != last_status or current.get('updates'):
                    message = current.get('message', 'Processing...')
                    
                    # Add any queued updates
                    updates = current.get('updates', [])
                    if updates:
                        message += "\n\n**Updates:**"
                        for update in updates[-5:]:  # Show last 5 updates
                            message += f"\n• {update}"
                            
                    # Add progress if available
                    if current.get('percent', 0) > 0:
                        message += f"\n\nProgress: {current.get('percent')}%"
                    
                    # Add elapsed time
                    elapsed = int(asyncio.get_event_loop().time() - start_time)
                    message += f"\n\n⏱️ Elapsed time: {elapsed//60}m {elapsed%60}s"
                    
                    try:
                        await msg.edit(content=message)
                        # Clear processed updates
                        if 'updates' in current:
                            current['updates'] = []
                        last_status = status
                    except Exception as e:
                        logger.error(f"Failed to update progress message: {e}")
                
                # Wait before next update
                await asyncio.sleep(update_interval)
                
            # Final update
            final = active_tasks.get(task_id, {})
            final_status = final.get('status', 'unknown')
            final_message = final.get('message', 'Task completed')
            
            if final_status == 'completed':
                # If we have a result embed, use it
                result = final.get('result')
                if isinstance(result, discord.Embed):
                    await msg.edit(content=None, embed=result)
                elif isinstance(result, str):
                    await msg.edit(content=result)
                else:
                    await msg.edit(content=f"✅ {final_message}")
            elif final_status == 'failed':
                error = final.get('error', 'Unknown error')
                await msg.edit(content=f"❌ {final_message}\n\nError: {error}")
            else:
                await msg.edit(content=f"⚠️ Task timed out after {timeout//60} minutes")
        except Exception as e:
            logger.error(f"Error in progress updater: {e}")
            logger.error(traceback.format_exc())
        finally:
            # Clean up
            if task_id in active_tasks:
                del active_tasks[task_id]
    
    # Start the updater task
    updater = asyncio.create_task(update_progress_message())
    
    try:
        # Run the actual task
        result = await task_func(*args, progress=progress, **kwargs)
        
        # Store the result and update status
        progress['status'] = 'completed'
        progress['result'] = result
        progress['message'] = 'Task completed successfully!'
        
    except Exception as e:
        logger.error(f"Error in background task: {e}")
        logger.error(traceback.format_exc())
        progress['status'] = 'failed'
        progress['error'] = str(e)
        progress['message'] = 'Task failed'
    
    # Wait for the updater to finish
    await updater


def update_task_progress(task_id: str, percent: int, message: Optional[str] = None, add_update: Optional[str] = None) -> bool:
    """
    Update the progress of a running task
    
    Args:
        task_id: The task ID
        percent: Progress percentage (0-100)
        message: Optional message to update
        add_update: An update to append to the updates list
        
    Returns:
        bool: Whether the update was successful
    """
    if task_id not in active_tasks:
        return False
        
    progress = active_tasks[task_id]
    
    # Update the progress
    progress['percent'] = max(0, min(100, percent))
    
    if message:
        progress['message'] = message
        
    if add_update:
        if 'updates' not in progress:
            progress['updates'] = []
        progress['updates'].append(add_update)
        
    return True


def background_task(initial_message: str = "⏳ Processing your request...", update_interval: int = 10):
    """
    Decorator to run a command as a background task with progress tracking.
    
    Example usage:
        @server_group.command()
        @background_task("Downloading server logs...")
        async def download_logs(self, ctx, server_name: str, progress=None):
            # The progress parameter is injected by the decorator
            progress['message'] = "Connecting to server..."
            ... long operation ...
            return embed  # Return value becomes the result
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, ctx, *args, **kwargs):
            return await run_task_with_progress(
                ctx, 
                func,
                self, ctx, *args,
                initial_message=initial_message,
                update_interval=update_interval,
                **kwargs
            )
        return wrapper
    return decorator