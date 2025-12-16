from __future__ import annotations

from typing import Optional

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import ServerSettings
from .models import (
    AIAssistFieldRequest,
    AIAssistFieldResponse,
    AutoDescribeRequest,
    AutoDescribeResponse,
    ChatHistorySaveRequest,
    ChatRequest,
    ChatResponse,
    ChatSession,
    ChatSessionSummary,
    DatabaseStatsResponse,
    DatalakeAddRequest,
    DatalakeInfo,
    DatalakeProjectInfo,
    DatalakeTestConnectionRequest,
    DatalakeTestConnectionResponse,
    DiagramRecord,
    DiagramSaveRequest,
    FieldUpdateRequest,
    FieldUpdateResponse,
    ProjectCreateRequest,
    ProjectInfo,
    ProjectUpdateRequest,
    QueryAssistRequest,
    QueryAssistResponse,
    QueryErrorAssistRequest,
    QueryErrorAssistResponse,
    QueryRecord,
    QueryRequest,
    QueryResponse,
    QuerySaveRequest,
    ReclaimSpaceRequest,
    ReclaimSpaceResponse,
    SchemaResponse,
    SyncDownloadRequest,
    SyncDownloadResponse,
    SyncUploadRequest,
    SyncUploadResponse,
    TableDeleteDataRequest,
    TableUpdateRequest,
    TableUpdateResponse,
    UndocumentedField,
)
from .runtime import DuckDBRuntime


def create_app(settings: Optional[ServerSettings] = None) -> FastAPI:
    settings = settings or ServerSettings.load()
    runtime = DuckDBRuntime(settings=settings)

    app = FastAPI(
        title="DBDocumenter API",
        version="0.1.0",
        description="HTTP API and chat backend for the DBDocumenter DuckDB assistant.",
    )

    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.state.settings = settings
    app.state.runtime = runtime

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        print(f"Validation error on {request.method} {request.url.path}:")
        print(f"  Errors: {exc.errors()}")
        print(f"  Body: {exc.body}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors(), "body": str(exc.body)},
        )

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        # Health check endpoint
        return {"status": "ok"}

    @app.get("/projects", response_model=list[ProjectInfo])
    async def list_projects() -> list[ProjectInfo]:
        projects = await runtime.list_projects()
        return [ProjectInfo(**project) for project in projects]

    @app.patch("/projects", response_model=ProjectInfo)
    async def update_project(request: ProjectUpdateRequest) -> ProjectInfo:
        try:
            info = await runtime.update_project_metadata(
                path=request.path,
                display_name=request.display_name,
                description=request.description,
                version=request.version,
                query_instructions=request.query_instructions,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return ProjectInfo(**info)

    @app.post("/projects", response_model=ProjectInfo, status_code=status.HTTP_201_CREATED)
    async def create_project(request: ProjectCreateRequest) -> ProjectInfo:
        try:
            info = await runtime.create_project(
                name=request.name, description=request.description, query_instructions=request.query_instructions
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return ProjectInfo(**info)

    @app.get("/schema", response_model=SchemaResponse)
    async def get_schema(project: Optional[str] = None, database: Optional[str] = None) -> SchemaResponse:
        schema_data = await runtime.get_schema(project=project, database=database)
        if not schema_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No DuckDB schema available.")
        return SchemaResponse(schema=schema_data)

    @app.get("/schema/tables", response_model=list[str])
    async def list_tables(project: Optional[str] = None, database: Optional[str] = None) -> list[str]:
        return await runtime.list_tables(project=project, database=database)

    @app.get("/schema/stats", response_model=DatabaseStatsResponse)
    async def get_database_stats(
        project: Optional[str] = None,
        database: Optional[str] = None,
    ) -> DatabaseStatsResponse:
        # Delegate to runtime (optimized)
        return await runtime.get_database_stats(project=project, database=database)

    @app.get("/schema/fields/undocumented", response_model=list[UndocumentedField])
    async def undocumented_fields(
        table: str,
        project: Optional[str] = None,
        database: Optional[str] = None,
    ) -> list[UndocumentedField]:
        if not table:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parameter 'table' is required.")
        records = await runtime.list_undocumented_fields(project=project, database=database, table=table)
        return [UndocumentedField(**record) for record in records]

    @app.post("/schema/field/update", response_model=FieldUpdateResponse)
    async def update_field(request: FieldUpdateRequest) -> FieldUpdateResponse:
        try:
            result = await runtime.update_field_metadata(
                project=request.project,
                database=request.database,
                table=request.table,
                field=request.field,
                short_description=request.short_description,
                long_description=request.long_description,
                nullability=request.nullability,
                data_type=request.data_type,
                values=request.values,
                relationships=[rel.dict(by_alias=True) for rel in request.relationships or []],
                new_field_name=request.new_field_name,
                allow_null=request.allow_null,
                ignored=request.ignored,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return FieldUpdateResponse(table=request.table, field=result["field"], metadata=result["metadata"])

    @app.post("/schema/table/update", response_model=TableUpdateResponse)
    async def update_table(request: TableUpdateRequest) -> TableUpdateResponse:
        try:
            result = await runtime.update_table_metadata(
                project=request.project,
                database=request.database,
                table=request.table,
                short_description=request.short_description,
                long_description=request.long_description,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return TableUpdateResponse(table=result["table"], metadata=result["metadata"])

    @app.delete("/schema/table/{table}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_table(
        table: str,
        project: Optional[str] = None,
        database: Optional[str] = None,
    ) -> Response:
        try:
            await runtime.delete_table(project=project, database=database, table=table)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/schema/table/delete-data")
    async def delete_table_data(request: TableDeleteDataRequest) -> dict:
        try:
            result = await runtime.delete_table_data(
                project=request.project,
                database=request.database,
                table=request.table,
                mode=request.mode,
                keep_count=request.keep_count,
                sort_column=request.sort_column,
                sort_order=request.sort_order,
                filter_condition=request.filter_condition,
            )
            return result
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    @app.post("/schema/field/describe", response_model=AutoDescribeResponse)
    async def auto_describe(request: AutoDescribeRequest) -> AutoDescribeResponse:
        try:
            description = await runtime.auto_describe_field(
                project=request.project,
                database=request.database,
                table=request.table,
                field=request.field,
                current_short_description=request.current_short_description,
                current_long_description=request.current_long_description,
                data_type=request.data_type,
                description_type=request.description_type,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            import traceback
            error_detail = f"Failed to generate AI description: {str(exc)}\n{traceback.format_exc()}"
            print(error_detail)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI generation failed: {str(exc)}"
            ) from exc
        return AutoDescribeResponse(description=description)

    @app.post("/schema/field/ai-assist", response_model=AIAssistFieldResponse)
    async def ai_assist_field(request: AIAssistFieldRequest) -> AIAssistFieldResponse:
        try:
            result = await runtime.ai_assist_field(
                project=request.project,
                database=request.database,
                table=request.table,
                field=request.field,
            )
            return result
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            import traceback
            error_detail = f"Failed to generate AI assist: {str(exc)}\n{traceback.format_exc()}"
            print(error_detail)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI assist failed: {str(exc)}"
            ) from exc

    @app.get("/diagrams", response_model=list[DiagramRecord])
    async def list_diagrams(project: Optional[str] = None, database: Optional[str] = None) -> list[DiagramRecord]:
        diagrams = await runtime.list_diagrams(project=project, database=database)
        return [DiagramRecord(**diagram) for diagram in diagrams]

    @app.post("/diagrams", response_model=DiagramRecord, status_code=status.HTTP_201_CREATED)
    async def save_diagram(request: DiagramSaveRequest) -> DiagramRecord:
        try:
            record = await runtime.save_diagram(
                project=request.project,
                database=request.database,
                name=request.name,
                description=request.description,
                tables=[table.dict() for table in request.tables],
                diagram_id=request.diagram_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return DiagramRecord(**record)

    @app.delete(
        "/diagrams/{diagram_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
    )
    async def delete_diagram(
        diagram_id: str,
        project: Optional[str] = None,
        database: Optional[str] = None,
    ) -> Response:
        try:
            await runtime.delete_diagram(project=project, database=database, diagram_id=diagram_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/queries", response_model=list[QueryRecord])
    async def list_queries(project: Optional[str] = None, database: Optional[str] = None) -> list[QueryRecord]:
        records = await runtime.list_queries(project=project, database=database)
        return [QueryRecord(**record) for record in records]

    @app.post("/queries", response_model=QueryRecord, status_code=status.HTTP_201_CREATED)
    async def save_query(request: QuerySaveRequest) -> QueryRecord:
        try:
            record = await runtime.save_query(
                project=request.project,
                database=request.database,
                name=request.name,
                description=request.description,
                sql=request.sql,
                limit=request.limit,
                query_id=request.query_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return QueryRecord(**record)

    @app.delete(
        "/queries/{query_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
    )
    async def delete_query(query_id: str, project: Optional[str] = None, database: Optional[str] = None) -> Response:
        try:
            await runtime.delete_query(project=project, database=database, query_id=query_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/query", response_model=QueryResponse)
    async def run_query(request: QueryRequest) -> QueryResponse:
        try:
            print(
                f"DEBUG /query: sql={request.sql[:50]}..., project={request.project}, "
                f"database={request.database}, limit={request.limit}"
            )
            result = await runtime.run_sql(
                sql=request.sql,
                project=request.project,
                database=request.database,
                limit=request.limit,
            )
        except ValueError as exc:
            print(f"ERROR /query ValueError: {exc}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            print(f"ERROR /query Exception: {exc}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

        return QueryResponse(
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            truncated=result.truncated,
            database=result.database,
            project=result.project,
            message=result.message,
        )

    @app.post("/query/assist", response_model=QueryAssistResponse)
    async def assist_query(request: QueryAssistRequest) -> QueryAssistResponse:
        try:
            sql = await runtime.assist_query(
                sql=request.sql,
                project=request.project,
                database=request.database,
            )
            return QueryAssistResponse(sql=sql)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI assistance failed: {str(exc)}"
            ) from exc

    @app.post("/query/assist-error", response_model=QueryErrorAssistResponse)
    async def assist_query_error(request: QueryErrorAssistRequest) -> QueryErrorAssistResponse:
        try:
            result = await runtime.assist_query_error(
                sql=request.sql,
                error=request.error,
                project=request.project,
                database=request.database,
            )
            return QueryErrorAssistResponse(**result)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI assistance failed: {str(exc)}"
            ) from exc

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        try:
            payload = await runtime.run_chat(
                message=request.message,
                reset=request.reset,
                project=request.project,
                database=request.database,
                file_content=request.file_content,
                filename=request.filename,
                session_id=request.session_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        return ChatResponse(**payload)

    @app.post("/chat/stream")
    async def chat_stream(request: ChatRequest):
        import json

        from starlette.responses import StreamingResponse

        async def event_generator():
            try:
                async for chunk in runtime.run_chat_stream(
                    message=request.message,
                    reset=request.reset,
                    project=request.project,
                    database=request.database,
                    file_content=request.file_content,
                    filename=request.filename,
                    session_id=request.session_id,
                    images=request.images,
                ):
                    yield f"data: {json.dumps(chunk)}\n\n"
            except Exception as exc:
                error_data = {"error": str(exc), "type": "error"}
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Chat History endpoints ------------------------------------------------

    @app.get("/chat/history", response_model=list[ChatSessionSummary])
    async def list_chat_history(project: str) -> list[ChatSessionSummary]:
        return runtime.chat_history_manager.list_sessions(project)

    @app.get("/chat/history/{session_id}", response_model=ChatSession)
    async def get_chat_session(session_id: str, project: str) -> ChatSession:
        session = runtime.chat_history_manager.get_session(project, session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
        return session

    @app.post("/chat/history", response_model=ChatSession)
    async def save_chat_session(request: ChatHistorySaveRequest) -> ChatSession:
        return runtime.chat_history_manager.save_session(request.project, request.messages)

    @app.delete("/chat/history/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_chat_session(session_id: str, project: str) -> Response:
        if not runtime.chat_history_manager.delete_session(project, session_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Datalake sync endpoints -----------------------------------------------

    @app.get("/datalakes", response_model=list[DatalakeInfo])
    async def list_datalakes() -> list[DatalakeInfo]:
        """List all configured datalakes."""
        datalakes = await runtime.list_datalakes()
        return [DatalakeInfo(**dl) for dl in datalakes]

    @app.get("/datalakes/{datalake_name}/projects", response_model=list[DatalakeProjectInfo])
    async def list_datalake_projects(datalake_name: str) -> list[DatalakeProjectInfo]:
        """List projects in a specific datalake."""
        try:
            projects = await runtime.list_datalake_projects(datalake_name)
            return [DatalakeProjectInfo(**p) for p in projects]
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @app.post("/sync/download", response_model=SyncDownloadResponse)
    async def download_project(request: SyncDownloadRequest) -> SyncDownloadResponse:
        """Download a project from a datalake."""
        try:
            result = await runtime.download_project_from_datalake(
                datalake_name=request.datalake_name,
                project_name=request.project_name,
                version=request.version,
                overwrite=request.overwrite,
                rename_existing=request.rename_existing,
            )
            return SyncDownloadResponse(**result)
        except (ValueError, FileExistsError) as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Download failed: {str(exc)}",
            ) from exc

    @app.post("/sync/upload", response_model=SyncUploadResponse)
    async def upload_project(request: SyncUploadRequest) -> SyncUploadResponse:
        """Upload a project to a datalake."""
        try:
            result = await runtime.upload_project_to_datalake(
                datalake_name=request.datalake_name,
                project_path=request.project_path,
                new_version=request.new_version,
                schema_only=request.schema_only,
            )
            return SyncUploadResponse(**result)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload failed: {str(exc)}",
            ) from exc

    @app.post("/datalakes/test", response_model=DatalakeTestConnectionResponse)
    async def test_datalake_connection(
        request: DatalakeTestConnectionRequest,
    ) -> DatalakeTestConnectionResponse:
        """Test datalake connection and list available containers."""
        try:
            result = await runtime.test_datalake_connection(
                type=request.type,
                connection_string=request.connection_string,
            )
            return DatalakeTestConnectionResponse(**result)
        except Exception as exc:
            return DatalakeTestConnectionResponse(
                success=False,
                message=str(exc),
                containers=[],
            )

    @app.post("/datalakes", response_model=DatalakeInfo, status_code=status.HTTP_201_CREATED)
    async def add_datalake(request: DatalakeAddRequest) -> DatalakeInfo:
        """Add a new datalake configuration."""
        try:
            result = await runtime.add_datalake(
                name=request.name,
                connection_string=request.connection_string,
                type=request.type,
                container_name=request.container_name,
            )
            return DatalakeInfo(**result)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    @app.delete("/datalakes/{datalake_name}", status_code=status.HTTP_204_NO_CONTENT)
    async def remove_datalake(datalake_name: str) -> Response:
        """Remove a datalake configuration."""
        removed = await runtime.remove_datalake(datalake_name)
        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Datalake '{datalake_name}' not found",
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.delete("/datalakes/{datalake_name}/projects/{project_name}/{version}")
    async def delete_datalake_project(datalake_name: str, project_name: str, version: str) -> dict:
        """Delete a project version from a datalake."""
        try:
            await runtime.delete_datalake_project(datalake_name, project_name, version)
            return {"message": f"Deleted project '{project_name}' version {version}"}
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    @app.post("/schema/reclaim-space", response_model=ReclaimSpaceResponse)
    async def reclaim_space(request: ReclaimSpaceRequest) -> ReclaimSpaceResponse:
        try:
            return await runtime.reclaim_space(
                project=request.project,
                database=request.database,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    @app.delete("/schema/field/{table}/{field}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_field(
        table: str,
        field: str,
        project: Optional[str] = None,
        database: Optional[str] = None,
    ) -> Response:
        try:
            await runtime.delete_field(project=project, database=database, table=table, field=field)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/schema/enrich")
    async def enrich_table(
        file: UploadFile = File(...),
        table: str = Form(...),
        project: Optional[str] = Form(None),
        database: Optional[str] = Form(None),
    ) -> dict:
        try:
            content = await file.read()
            result = await runtime.enrich_table_from_file(
                project=project,
                database=database,
                table=table,
                filename=file.filename or "unknown",
                file_content=content,
            )
            return result
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Enrichment failed: {str(exc)}"
            ) from exc

    @app.get("/projects/{project_name}/documentation")
    async def get_project_documentation(project_name: str):
        runtime = app.state.runtime
        # Ensure project is loaded
        await runtime._ensure_project_locked(project=project_name, database=None)
        schema = runtime.schema_manager.schema
        
        markdown = f"# Project: {schema.get('project_display_name', project_name)}\n\n"
        if schema.get('project_description'):
            markdown += f"{schema['project_description']}\n\n"
            
        markdown += f"**Version:** {schema.get('version', '1.0.0')}\n\n"
        
        tables = schema.get('tables', {})
        markdown += "## Tables\n\n"
        
        for table_name, table_data in sorted(tables.items()):
            markdown += f"### {table_name}\n\n"
            
            short_desc = table_data.get('short_description', '') or table_data.get('description', '')
            long_desc = table_data.get('long_description', '')
            
            if short_desc:
                markdown += f"{short_desc}\n\n"
            if long_desc and long_desc != short_desc:
                markdown += f"{long_desc}\n\n"
                
            fields = table_data.get('fields', {})
            if fields:
                markdown += "| Field | Type | Nullable | Description |\n"
                markdown += "| --- | --- | --- | --- |\n"
                
                for field_name, field_data in fields.items():
                    dtype = field_data.get('data_type', 'UNKNOWN')
                    nullable = "Yes" if field_data.get('allow_null', True) else "No"
                    
                    short_desc = field_data.get('short_description', '') or field_data.get('description', '')
                    long_desc = field_data.get('long_description', '')
                    
                    desc_parts = []
                    if short_desc:
                        desc_parts.append(short_desc)
                    if long_desc and long_desc != short_desc:
                        desc_parts.append(long_desc)
                    
                    final_desc = " - ".join(desc_parts).replace('\n', ' ')
                        
                    markdown += f"| **{field_name}** | {dtype} | {nullable} | {final_desc} |\n"
                markdown += "\n"
                
        markdown += "## Relationships & Coverage\n\n"
        
        # Calculate coverage and unmatched values
        has_relationships = False
        
        for table_name, table_data in sorted(tables.items()):
            relationships = table_data.get('relationships', [])
            for rel in relationships:
                field_name = rel.get('field')
                related_table = rel.get('related_table')
                related_field = rel.get('related_field')
                
                if not field_name or not related_table or not related_field:
                    continue
                
                has_relationships = True
                markdown += f"### {table_name}.{field_name} -> {related_table}.{related_field}\n\n"
                
                # Calculate coverage
                try:
                    # Coverage query
                    count_sql = f"""
                        SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN "{field_name}" IN (
                                SELECT "{related_field}" FROM "{related_table}" WHERE "{related_field}" IS NOT NULL
                            ) THEN 1 ELSE 0 END) as matched
                        FROM "{table_name}"
                        WHERE "{field_name}" IS NOT NULL AND CAST("{field_name}" AS VARCHAR) != ''
                    """
                    res = runtime.query_tool.execute_structured(count_sql)
                    if res.rows and res.rows[0]:
                        total = res.rows[0][0] or 0
                        matched = res.rows[0][1] or 0
                        coverage = (matched / total * 100) if total > 0 else 100
                        markdown += f"- **Coverage:** {coverage:.2f}% ({matched}/{total})\n"
                        
                        if coverage < 100:
                            # Unmatched values query
                            unmatched_sql = f"""
                                SELECT DISTINCT "{field_name}"
                                FROM "{table_name}"
                                WHERE "{field_name}" IS NOT NULL 
                                  AND CAST("{field_name}" AS VARCHAR) != ''
                                  AND "{field_name}" NOT IN (
                                    SELECT "{related_field}" 
                                    FROM "{related_table}" 
                                    WHERE "{related_field}" IS NOT NULL
                                  )
                                LIMIT 10
                            """
                            res_unmatched = runtime.query_tool.execute_structured(unmatched_sql)
                            if res_unmatched.rows:
                                markdown += "- **Top Unmatched Values:**\n"
                                for row in res_unmatched.rows:
                                    markdown += f"  - `{row[0]}`\n"
                except Exception as e:
                    markdown += f"- **Error calculating coverage:** {str(e)}\n"
                
                markdown += "\n"
        
        if not has_relationships:
            markdown += "No relationships defined.\n"

        return {"markdown": markdown}

    @app.get("/projects/{project_name}/export/llm")
    async def export_project_llm(project_name: str):
        runtime = app.state.runtime
        await runtime._ensure_project_locked(project=project_name, database=None)
        schema = runtime.schema_manager.schema.copy()
        
        # Remove unnecessary fields
        if 'diagrams' in schema:
            del schema['diagrams']
        if 'queries' in schema:
            del schema['queries']
            
        # Clean up tables
        if 'tables' in schema:
            for table_data in schema['tables'].values():
                if 'layout' in table_data:
                    del table_data['layout']
                # Maybe remove other UI specific fields if any
                
        return schema
    return app


app = create_app()

__all__ = ["create_app", "app"]
