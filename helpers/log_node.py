import inspect

from api.ws_manager_graph import ws_manager_graph
from utils.execution_events import (
    begin_node_execution,
    build_node_execution_message,
    finish_node_execution,
)


def _get_session_id(config):
    configurable = (config or {}).get("configurable", {})
    return configurable.get("thread_id")


def _is_graph_interrupt(error: BaseException) -> bool:
    return error.__class__.__name__ == "GraphInterrupt"


def log_node(graph_name, name, fn):

    if inspect.iscoroutinefunction(fn):

        async def async_wrapper(state, config):
            session_id = _get_session_id(config)
            execution_context = begin_node_execution(graph_name, name, session_id)

            print(f"[NODE START] {graph_name}/{name}")

            if session_id:
                await ws_manager_graph.send(
                    session_id,
                    build_node_execution_message(execution_context, status="started"),
                )

            try:
                result = await fn(state, config)
            except Exception as error:
                if session_id:
                    status = "paused" if _is_graph_interrupt(error) else "failed"
                    await ws_manager_graph.send(
                        session_id,
                        build_node_execution_message(
                            execution_context,
                            status=status,
                            error=error,
                        ),
                    )
                raise
            except BaseException as error:
                if session_id and _is_graph_interrupt(error):
                    await ws_manager_graph.send(
                        session_id,
                        build_node_execution_message(
                            execution_context,
                            status="paused",
                            error=error,
                        ),
                    )
                raise
            else:
                print(f"[NODE END] {graph_name}/{name}")

                if session_id:
                    await ws_manager_graph.send(
                        session_id,
                        build_node_execution_message(
                            execution_context,
                            status="completed",
                            result=result,
                        ),
                    )

                return result
            finally:
                finish_node_execution(execution_context)

        return async_wrapper

    else:

        def sync_wrapper(state, config):
            session_id = _get_session_id(config)
            execution_context = begin_node_execution(graph_name, name, session_id)

            print(f"[NODE START] {graph_name}/{name}")

            if session_id:
                ws_manager_graph.send_nowait(
                    session_id,
                    build_node_execution_message(execution_context, status="started"),
                )

            try:
                result = fn(state, config)
            except Exception as error:
                if session_id:
                    status = "paused" if _is_graph_interrupt(error) else "failed"
                    ws_manager_graph.send_nowait(
                        session_id,
                        build_node_execution_message(
                            execution_context,
                            status=status,
                            error=error,
                        ),
                    )
                raise
            except BaseException as error:
                if session_id and _is_graph_interrupt(error):
                    ws_manager_graph.send_nowait(
                        session_id,
                        build_node_execution_message(
                            execution_context,
                            status="paused",
                            error=error,
                        ),
                    )
                raise
            else:
                print(f"[NODE END] {graph_name}/{name}")

                if session_id:
                    ws_manager_graph.send_nowait(
                        session_id,
                        build_node_execution_message(
                            execution_context,
                            status="completed",
                            result=result,
                        ),
                    )

                return result
            finally:
                finish_node_execution(execution_context)

        return sync_wrapper
