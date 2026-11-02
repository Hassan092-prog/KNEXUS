"""Disposable PostgreSQL/pgvector integration tests."""
import os
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError


def _pg_details(error):
    # SQLAlchemy's asyncpg wrapper carries SQLSTATE; native asyncpg carries constraint_name.
    wrapper = getattr(error, "orig", None) or error
    state = getattr(wrapper, "sqlstate", None)
    native = getattr(wrapper, "driver_exception", None)
    if native is None:
        native = getattr(wrapper, "orig", None)
    if native is None:
        raise AssertionError("adapter did not expose its native driver exception")
    return state, getattr(native, "constraint_name", None)


def _assert_pg_constraint(error, state, constraint):
    actual_state, actual_constraint = _pg_details(error)
    assert actual_state == state, f"SQLSTATE mismatch: expected {state}, got {actual_state}"
    assert actual_constraint == constraint, f"constraint mismatch: expected {constraint}, got {actual_constraint}"


def test_asyncpg_wrapped_error_offline():
    native = SimpleNamespace(sqlstate="23514", constraint_name="ck_jobs_state_consistency")
    class AdapterError(Exception):
        def __init__(self, driver):
            super().__init__("synthetic")
            self.orig = driver
            self.sqlstate = driver.sqlstate
        @property
        def driver_exception(self):
            return self.orig
    error = IntegrityError("synthetic SQL", {}, AdapterError(native))
    _assert_pg_constraint(error, "23514", "ck_jobs_state_consistency")
    with pytest.raises(AssertionError, match="SQLSTATE mismatch"):
        _assert_pg_constraint(error, "23503", "ck_jobs_state_consistency")
    with pytest.raises(AssertionError, match="constraint mismatch"):
        _assert_pg_constraint(error, "23514", "wrong_constraint")


def _guard_database_url():
    url = os.environ.get("DATABASE_URL")
    expected = os.environ.get("KNEXUS_VERIFY_EXPECTED_DATABASE_URL")
    if not url or url != expected:
        raise AssertionError("DATABASE_URL does not match KNEXUS_VERIFY_EXPECTED_DATABASE_URL")
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+asyncpg":
        raise AssertionError(f"Expected postgresql+asyncpg, got {parsed.scheme}")
    if parsed.hostname != "127.0.0.1":
        raise AssertionError(f"Loopback target required (127.0.0.1), got {parsed.hostname}")
    if parsed.path == "/knexus" and parsed.port == 5435 and parsed.username == "knexus_admin":
        raise AssertionError("Guarded check rejected target: points to shared development database!")
    assert parsed.username == os.environ.get("POSTGRES_USER")
    assert parsed.password == os.environ.get("POSTGRES_PASSWORD")
    assert parsed.path == "/" + os.environ.get("POSTGRES_DB")
    assert parsed.port == int(os.environ.get("POSTGRES_PORT"))
    return url


@pytest_asyncio.fixture
async def pg_engine():
    if os.environ.get("KNEXUS_ENABLE_DISPOSABLE_PG_TESTS") not in ("1", "true", "TRUE", "yes", "YES"):
        pytest.skip("Disposable PostgreSQL test skipped; set KNEXUS_ENABLE_DISPOSABLE_PG_TESTS=1 to run against an isolated target")
    url = _guard_database_url()
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


def _models():
    from app.models import Document, DocumentChunk, Embedding, IngestionJob, Organization, User
    from app.models import VECTOR_DIMENSIONS
    return Document,DocumentChunk,Embedding,IngestionJob,Organization,User,VECTOR_DIMENSIONS


async def _base(engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    Document,Chunk,_,_,Organization,User,_=_models()
    Session=async_sessionmaker(engine,expire_on_commit=False)
    suffix=uuid4().hex
    org1,org2,user1,user2,doc,chunk=(uuid4() for _ in range(6))
    async with Session() as s:
        s.add_all([
            Organization(id=org1,name="Synthetic one",slug="synthetic-one-"+suffix),
            Organization(id=org2,name="Synthetic two",slug="synthetic-two-"+suffix),
        ])
        await s.flush()
        s.add_all([
            User(id=user1,org_id=org1,email="one-"+suffix+"@example.invalid",
                 full_name="Synthetic one",role="orgadmin",is_active=True),
            User(id=user2,org_id=org2,email="two-"+suffix+"@example.invalid",
                 full_name="Synthetic two",role="orgadmin",is_active=True),
        ])
        await s.flush()
        document=Document(
            id=doc,org_id=org1,uploaded_by=user1,title="Synthetic PDF",
            source_type="pdf",original_filename="source.pdf",file_size_bytes=32,
            allowed_roles=["employee"],chunk_count=1,metadata_json={"run":suffix},
        )
        s.add(document)
        await s.flush()
        s.add(Chunk(
            id=chunk,org_id=org1,document_id=doc,chunk_index=0,
            content="Synthetic source text.",page=1,token_count=4,
            source_metadata={"page_label":"1"},
        ))
        await s.flush()
        await s.commit()
    return {"org1":org1,"org2":org2,"user1":user1,"user2":user2,"doc":doc,"chunk":chunk}

async def _expect(engine, sql, params, state, constraint):
    try:
        async with engine.begin() as conn:
            await conn.execute(text(sql),params)
    except IntegrityError as error:
        _assert_pg_constraint(error,state,constraint)
    else:
        pytest.fail(f"expected SQLSTATE {state} / {constraint}; insert succeeded")


async def _expect_vector_dimension_error(engine, r):
    from asyncpg.exceptions import DataError as NativeAsyncpgDataError

    vector = "[" + ",".join(["0"] * 383) + "]"
    sql = """INSERT INTO embeddings
    (id,org_id,document_id,chunk_id,embedding,model_name,model_revision)
    VALUES (:id,:org,:doc,:chunk,CAST(:vector AS vector),
            'synthetic-invalid-dimension','synthetic-revision')"""
    try:
        async with engine.begin() as conn:
            await conn.execute(text(sql), {
                "id": uuid4(), "org": r["org1"], "doc": r["doc"],
                "chunk": r["chunk"], "vector": vector,
            })
    except DBAPIError as error:
        state, constraint = _pg_details(error)
        wrapper = getattr(error, "orig", None) or error
        native = getattr(wrapper, "driver_exception", None)
        if native is None:
            native = getattr(wrapper, "orig", None)
        assert isinstance(native, NativeAsyncpgDataError)
        assert state == "22000", f"expected pgvector SQLSTATE 22000, got {state}"
        assert constraint is None, "dimension coercion must not masquerade as a named constraint"
    else:
        pytest.fail("expected asyncpg DataError with SQLSTATE 22000 for 383-dimensional vector")


@pytest.mark.asyncio
async def test_pgvector_rejects_wrong_dimension_with_specific_driver_error(pg_engine):
    r = await _base(pg_engine)
    catalog_sql = text("""
        SELECT pg_catalog.format_type(a.atttypid, a.atttypmod)
        FROM pg_catalog.pg_attribute AS a
        JOIN pg_catalog.pg_class AS c ON c.oid = a.attrelid
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname = 'embeddings'
          AND a.attname = 'embedding'
          AND a.attnum > 0
          AND NOT a.attisdropped
    """)
    async with pg_engine.connect() as conn:
        actual_type = await conn.scalar(catalog_sql)
    assert actual_type == "vector(384)", (
        f"expected public.embeddings.embedding to be vector(384), got {actual_type!r}"
    )
    await _expect_vector_dimension_error(pg_engine, r)


@pytest.mark.asyncio
async def test_tenant_composite_foreign_keys(pg_engine):
    r=await _base(pg_engine)
    await _expect(pg_engine,
        """INSERT INTO documents
        (id,org_id,uploaded_by,title,source_type,original_filename,file_size_bytes,allowed_roles)
        VALUES (:id,:org,:user,'bad uploader','pdf','bad.pdf',1,CAST('["employee"]' AS jsonb))""",
        {"id":uuid4(),"org":r["org1"],"user":r["user2"]},
        "23503","fk_documents_uploader_same_org")
    await _expect(pg_engine,
        """INSERT INTO document_chunks(id,org_id,document_id,chunk_index,content)
        VALUES (:id,:org,:doc,0,'cross-tenant chunk')""",
        {"id":uuid4(),"org":r["org2"],"doc":r["doc"]},
        "23503","fk_chunks_document_same_org")
    vector="["+",".join(["0"]*384)+"]"
    await _expect(pg_engine,
        """INSERT INTO embeddings
        (id,org_id,document_id,chunk_id,embedding,model_name,model_revision)
        VALUES (:id,:org,:doc,:chunk,CAST(:vector AS vector(384)),'synthetic','revision')""",
        {"id":uuid4(),"org":r["org2"],"doc":r["doc"],"chunk":r["chunk"],"vector":vector},
        "23503","fk_embeddings_chunk_same_org_document")
    await _expect(pg_engine,
        """INSERT INTO ingestion_jobs(id,org_id,document_id,attempt_number,status)
        VALUES (:id,:org,:doc,1,'queued')""",
        {"id":uuid4(),"org":r["org2"],"doc":r["doc"]},
        "23503","fk_jobs_document_same_org")


def _job_sql():
    return """INSERT INTO ingestion_jobs
    (id,org_id,document_id,attempt_number,status,chunks_processed,total_chunks,
     started_at,finished_at,failure_code,failure_message)
    VALUES (:id,:org,:doc,:attempt,:status,:processed,:total,
     CASE WHEN :started THEN now() ELSE NULL END,
     CASE WHEN :finished THEN now() ELSE NULL END,:code,:message)"""


def _job(r,**changes):
    row={"id":uuid4(),"org":r["org1"],"doc":r["doc"],"attempt":1,
         "status":"queued","processed":0,"total":None,"started":False,
         "finished":False,"code":None,"message":None}
    row.update(changes)
    return row


@pytest.mark.asyncio
async def test_job_lifecycle_progress_and_six_whitespace_cases(pg_engine):
    r=await _base(pg_engine)
    valid=_job(r)
    async with pg_engine.begin() as conn:
        await conn.execute(text(_job_sql()),valid)
        await conn.execute(
            text("UPDATE ingestion_jobs SET status='processing',started_at=now() WHERE id=:id"),
            {"id":valid["id"]},
        )
        await conn.execute(
            text("UPDATE ingestion_jobs SET status='complete',finished_at=now(),total_chunks=0 WHERE id=:id"),
            {"id":valid["id"]},
        )

    # Every status is otherwise valid; each orphaned failure field is tested alone.
    attempt=10
    for status in ("queued","processing","complete"):
        state=_job(r,attempt=attempt,status=status)
        if status=="processing":
            state.update(started=True)
        elif status=="complete":
            state.update(started=True,finished=True,total=0)
        code_only=dict(state, id=uuid4(), attempt=attempt, code="PROCESSING_FAILED", message=None)
        await _expect(pg_engine,_job_sql(),code_only,"23514","ck_jobs_state_consistency")
        attempt+=1
        message_only=dict(state, id=uuid4(), attempt=attempt, code=None, message="must be absent")
        await _expect(pg_engine,_job_sql(),message_only,"23514","ck_jobs_state_consistency")
        attempt+=1

    # Existing progress/terminal-state rules remain independently exercised.
    await _expect(
        pg_engine,_job_sql(),
        _job(r,attempt=attempt,status="processing",started=False),
        "23514","ck_jobs_state_consistency",
    )
    attempt+=1
    await _expect(
        pg_engine,_job_sql(),
        _job(r,attempt=attempt,status="complete",started=True,finished=True,total=1),
        "23514","ck_jobs_state_consistency",
    )
    attempt+=1
    await _expect(
        pg_engine,_job_sql(),
        _job(r,attempt=attempt,status="processing",started=True,total=0,processed=1),
        "23514","ck_jobs_chunk_counts",
    )

    # Failed-state required fields are tested one at a time.
    await _expect(
        pg_engine,_job_sql(),
        _job(r,attempt=30,status="failed",finished=True,code=None,message="failure"),
        "23514","ck_jobs_state_consistency",
    )
    await _expect(
        pg_engine,_job_sql(),
        _job(r,attempt=31,status="failed",finished=True,code="PROCESSING_FAILED",message=None),
        "23514","ck_jobs_state_consistency",
    )
    await _expect(
        pg_engine,_job_sql(),
        _job(r,attempt=32,status="failed",finished=False,code="PROCESSING_FAILED",message="failure"),
        "23514","ck_jobs_state_consistency",
    )

    whitespace=["","   ","\t\t","\r\n\r\n"," \t\r\n\v\f"]
    for attempt,message in enumerate(whitespace,start=40):
        await _expect(
            pg_engine,_job_sql(),
            _job(r,attempt=attempt,status="failed",finished=True,
                 code="PROCESSING_FAILED",message=message),
            "23514","ck_jobs_state_consistency",
        )
    async with pg_engine.begin() as conn:
        await conn.execute(
            text(_job_sql()),
            _job(r,attempt=50,status="failed",finished=True,
                 code="PROCESSING_FAILED",message=" \tvalid failure\r\n "),
        )

@pytest.mark.asyncio
async def test_demo_seed_idempotence_across_sessions_and_inactive_rejection(pg_engine):
    from sqlalchemy import delete, func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.core.demo_identity import build_demo_actor
    from app.db.demo_seed import DemoSeedConflictError,build_demo_records,seed_demo_identity
    from app.models import Organization,User

    Session=async_sessionmaker(pg_engine,expire_on_commit=False)
    actor=build_demo_actor()

    # A caller rollback must leave no newly seeded rows in a fresh session.
    async with Session() as s:
        returned=await seed_demo_identity(s)
        assert returned==actor
        await s.rollback()
    async with Session() as s:
        assert await s.scalar(select(func.count()).select_from(Organization).where(Organization.id==actor.org_id))==0
        assert await s.scalar(select(func.count()).select_from(User).where(User.id==actor.user_id))==0

    # Commit once, then reseed from a distinct session and verify one row per ID.
    async with Session() as s:
        first=await seed_demo_identity(s)
        assert first==actor
        await s.commit()
    async with Session() as s:
        second=await seed_demo_identity(s)
        assert second==actor
        assert await s.scalar(select(func.count()).select_from(Organization).where(Organization.id==actor.org_id))==1
        assert await s.scalar(select(func.count()).select_from(User).where(User.id==actor.user_id))==1
        await s.commit()

    # Remove this test's committed reserved IDs before each inactive-record case.
    async with Session() as s:
        await s.execute(delete(User).where(User.id==actor.user_id))
        await s.execute(delete(Organization).where(Organization.id==actor.org_id))
        await s.commit()

    # Persist an inactive organization, then reject it in a fresh session.
    org,user=build_demo_records()
    org.is_active=False
    async with Session() as s:
        s.add(org)
        await s.flush()
        s.add(user)
        await s.flush()
        await s.commit()
    async with Session() as s:
        with pytest.raises(DemoSeedConflictError):
            await seed_demo_identity(s)
        await s.rollback()
    async with Session() as s:
        persisted_org=await s.get(Organization,actor.org_id)
        assert persisted_org is not None and persisted_org.is_active is False
        await s.execute(delete(User).where(User.id==actor.user_id))
        await s.execute(delete(Organization).where(Organization.id==actor.org_id))
        await s.commit()

    # Persist an inactive user, then reject it in a fresh session.
    org,user=build_demo_records()
    user.is_active=False
    async with Session() as s:
        s.add(org)
        await s.flush()
        s.add(user)
        await s.flush()
        await s.commit()
    async with Session() as s:
        with pytest.raises(DemoSeedConflictError):
            await seed_demo_identity(s)
        await s.rollback()
    async with Session() as s:
        persisted_org=await s.get(Organization,actor.org_id)
        persisted_user=await s.get(User,actor.user_id)
        assert persisted_org is not None and persisted_org.is_active is True
        assert persisted_user is not None and persisted_user.is_active is False
        await s.execute(delete(User).where(User.id==actor.user_id))
        await s.execute(delete(Organization).where(Organization.id==actor.org_id))
        await s.commit()

@pytest.mark.asyncio
async def test_document_chunk_job_and_384_vector_round_trip(pg_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.models import Document,DocumentChunk,Embedding,IngestionJob,Organization,User,VECTOR_DIMENSIONS
    Session=async_sessionmaker(pg_engine,expire_on_commit=False)
    suffix=uuid4().hex
    org,user,doc,chunk,embedding_id,job_id=(uuid4() for _ in range(6))
    vector=[0.25]*VECTOR_DIMENSIONS
    async with Session() as s:
        s.add(Organization(id=org,name="Round trip",slug="roundtrip-"+suffix))
        await s.flush()
        s.add(User(id=user,org_id=org,email="roundtrip-"+suffix+"@example.invalid",
                   full_name="Round trip",role="orgadmin",is_active=True))
        await s.flush()
        s.add(Document(id=doc,org_id=org,uploaded_by=user,title="Round trip",
                       source_type="pdf",original_filename="roundtrip.pdf",
                       file_size_bytes=64,allowed_roles=["employee"],chunk_count=1,
                       metadata_json={"source":"synthetic"}))
        await s.flush()
        s.add(DocumentChunk(id=chunk,org_id=org,document_id=doc,chunk_index=0,
                            content="Persisted source content.",page=3,token_count=5,
                            source_metadata={"page_label":"3"}))
        await s.flush()
        s.add_all([
            Embedding(id=embedding_id,org_id=org,document_id=doc,chunk_id=chunk,
                      embedding=vector,model_name="all-MiniLM-L6-v2",
                      model_revision="synthetic-revision",is_active=True),
            IngestionJob(id=job_id,org_id=org,document_id=doc,attempt_number=1,
                         status="queued",chunks_processed=0),
        ])
        await s.flush()
        await s.commit()
    async with Session() as s:
        d=await s.get(Document,doc); c=await s.get(DocumentChunk,chunk)
        e=await s.get(Embedding,embedding_id); j=await s.get(IngestionJob,job_id)
        assert d is not None and d.original_filename=="roundtrip.pdf"
        assert d.metadata_json=={"source":"synthetic"}
        assert c is not None and c.page==3 and c.source_metadata=={"page_label":"3"}
        assert e is not None and len(e.embedding)==384==VECTOR_DIMENSIONS
        assert list(e.embedding)==vector
        assert j is not None and j.status=="queued" and j.chunks_processed==0
