from datetime import datetime
from typing import Optional
from uuid import uuid4
from sqlalchemy.exc import IntegrityError

from pydantic import UUID4
from WORKOUT_API.atleta.schemas import AtletaIn, AtletaOut, AtletaUpdate, AtletaOutCustom
from WORKOUT_API.atleta.models import AtletaModel
from WORKOUT_API.categorias.models import CategoriaModel
from WORKOUT_API.centro_treinamento.models import CentroTreinamentoModel


from fastapi import APIRouter, Body, HTTPException, Query, status
from fastapi_pagination import Page, paginate

from WORKOUT_API.contrib.dependencies import DatabaseDependency
from sqlalchemy.future import select

router = APIRouter()


@router.post(
    '/',
    summary='Criar um novo atleta',
    status_code=status.HTTP_201_CREATED,
    response_model=AtletaOut    
)

async def post(
    db_session: DatabaseDependency, 
    atleta_in: AtletaIn = Body(...)
):
    categoria_nome = atleta_in.categoria.nome
    centro_treinamento_nome = atleta_in.centro_treinamento.nome

    categoria = (await db_session.execute(
        select(CategoriaModel).filter_by(nome=categoria_nome))
    ).scalars().first()
    
    if not categoria:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f'A categoria {categoria_nome} não foi encontrada.'
        )
    
    centro_treinamento = (await db_session.execute(
        select(CentroTreinamentoModel).filter_by(nome=centro_treinamento_nome))
    ).scalars().first()
    
    if not centro_treinamento:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f'O centro de treinamento {centro_treinamento_nome} não foi encontrado.'
        )

    try:
        atleta_out = AtletaOut(id=uuid4(), created_at=datetime.utcnow(), **atleta_in.model_dump())
        atleta_model = AtletaModel(**atleta_out.model_dump(exclude={'categoria', 'centro_treinamento'}))
        atleta_model.categoria_id = categoria.pk_id
        atleta_model.centro_treinamento_id = centro_treinamento.pk_id
    except Exception:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Ocorreu um erro de duplicidade ao inserir os dados no banco.')


    db_session.add(atleta_model)

    try:
        await db_session.commit()
    except IntegrityError as e:
        await db_session.rollback()
        if 'cpf' in str(e.orig).lower():
            raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, detail=f'Já existe um atleta cadastrado com o cpf {atleta_in.cpf}')
        raise

    return atleta_out

@router.get(
    '/',
    summary='Consultar todos os atletas',
    status_code=status.HTTP_200_OK, 
    response_model=Page[AtletaOutCustom]
    
)
async def query(
    db_session: DatabaseDependency,
    nome: Optional[str] = Query(None, description='Filtrar pelo nome do atleta'),
    cpf: Optional[str] = Query(None, description='Filtrar pelo cpf do atleta')
    ) -> Page[AtletaOutCustom]:

    query_stmt = select(AtletaModel).join(AtletaModel.centro_treinamento).join(AtletaModel.categoria)

    if nome:
        query_stmt = query_stmt.filter(AtletaModel.nome.ilike(f'%{nome}%'))
    if cpf:
        query_stmt = query_stmt.filter(AtletaModel.cpf == cpf)

    atletas: list[AtletaModel] = (await db_session.execute(query_stmt)).scalars().all()

    atletas_custom = [
        AtletaOutCustom(
            nome=atleta.nome,
            centro_treinamento=atleta.centro_treinamento.nome,
            categoria=atleta.categoria.nome
        )
        for atleta in atletas
    ]

    return paginate(atletas_custom)


@router.get(
    '/{id}',
    summary='Consultar um atleta pelo id',
    status_code=status.HTTP_200_OK, 
    response_model=AtletaOut    
)
async def query(id: UUID4, db_session: DatabaseDependency) -> AtletaOut:
    atleta: AtletaOut = (
        await db_session.execute(select(AtletaModel).filter_by(id=id))
    ).scalars().first()

    if not atleta:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f'Atleta não encontrado no id {id}'
        )

    return atleta


@router.patch(
    '/{id}',
    summary='Editar um atleta pelo id',
    status_code=status.HTTP_200_OK, 
    response_model=AtletaOut    
)
async def query(id: UUID4, db_session: DatabaseDependency, atleta_up: AtletaUpdate = Body(...)) -> AtletaOut:
    atleta: AtletaOut = (
        await db_session.execute(select(AtletaModel).filter_by(id=id))
    ).scalars().first()

    if not atleta:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f'Atleta não encontrado no id {id}'
        )

    atleta_update = atleta_up.model_dump(exclude_unset=True)
    for key, values in atleta_update.items():
        setattr(atleta, key, values)

    await db_session.commit()
    await db_session.refresh(atleta)

    return atleta

@router.delete(
    '/{id}',
    summary='Deletar um atleta pelo id',
    status_code=status.HTTP_204_NO_CONTENT
)
async def query(id: UUID4, db_session: DatabaseDependency) -> None:
    atleta: AtletaOut = (
        await db_session.execute(select(AtletaModel).filter_by(id=id))
    ).scalars().first()

    if not atleta:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f'Atleta não encontrado no id {id}'
        )

    await db_session.delete(atleta)
    await db_session.commit()
