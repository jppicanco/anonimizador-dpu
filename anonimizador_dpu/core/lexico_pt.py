"""Léxico em português para distinguir nome de pessoa de vocabulário comum.

Motivo deste módulo
-------------------
A heurística original tratava qualquer sequência de palavras iniciadas por
maiúscula como possível nome de pessoa. Em peça judicial isso é desastroso:
decisões, acórdãos e despachos são cheios de títulos em caixa alta e de
expressões em caixa de título que não identificam ninguém — "PODER JUDICIÁRIO",
"PEDIDO DE UNIFORMIZAÇÃO", "REEXAME DE PROVA", "VIA ELEITA", "CONJUNTO
PROBATÓRIO", "FORNECIMENTO DE MEDICAMENTO NÃO INCORPORADO", "NAT JUS".

O resultado era uma lista de revisão com dezenas de falsos positivos. Isso não
é apenas incômodo: o revisor que precisa descartar cinquenta linhas inúteis
para de ler com atenção e passa a errar justamente no que importa. Uma
ferramenta ruidosa é uma ferramenta insegura.

O que o aplicativo deve remover é a **identificação de pessoas** — nome,
endereço, CPF e congêneres. Nome de medicamento, nome de recurso, nome de
sistema e expressão jurídica corrente não identificam ninguém e não devem ser
tocados.

Como o léxico é usado
---------------------
``TERMOS_NAO_PESSOA`` e ``PALAVRAS_FUNCIONAIS`` eliminam candidatos; ``PRENOMES``
e ``SOBRENOMES`` são a evidência positiva de que há uma pessoa ali. Nenhuma
lista é baixada: tudo é local, embutido no código e auditável.

Limite conhecido e assumido: um nome raro, grafado em caixa alta e sem rótulo
processual por perto, pode deixar de ser detectado automaticamente. Ver
``docs/LIMITACOES.md``.
"""

from __future__ import annotations

import unicodedata


def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos, para comparação com as listas."""
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn").lower()


def _conjunto(bruto: str) -> frozenset[str]:
    return frozenset(normalizar(t) for t in bruto.split() if len(t) > 1)


# ---------------------------------------------------------------------------
# Palavras funcionais: jamais aparecem dentro de um nome de pessoa.
# Os conectores legítimos de nome (de, da, do, das, dos, e) ficam de fora,
# porque são parte de nomes brasileiros.
# ---------------------------------------------------------------------------
_FUNCIONAIS = """
nao sim que qual quais quando onde como porque pois porem contudo todavia
entretanto embora caso se mas ou nem ja ainda apenas somente tambem mesmo
muito pouco mais menos bastante demais tao quanto todo toda todos todas
cada qualquer algum alguma alguns algumas nenhum nenhuma outro outra outros
outras tal tais este esta estes estas esse essa esses essas aquele aquela
aqueles aquelas isto isso aquilo seu sua seus suas meu minha nosso nossa
para por pelo pela pelos pelas com sem sob sobre entre ate apos antes durante
desde contra perante conforme segundo mediante salvo exceto inclusive
ser estar ter haver fazer poder dever ir vir dar ver saber querer
foi sao era eram sera serao seja sejam fosse fossem sendo sido
tem tinha tiveram tenha tenham havia houve haja
deve devem devera deverao podia podem podera poderao
nos vos lhe lhes ele ela eles elas voce voces
"""
PALAVRAS_FUNCIONAIS = _conjunto(_FUNCIONAIS)


# ---------------------------------------------------------------------------
# Vocabulário que não identifica pessoa.
# ---------------------------------------------------------------------------
#: Órgãos, instituições e poderes.
_INSTITUICOES = """
poder poderes judiciario judiciaria executivo legislativo ministerio publico
justica tribunal tribunais federal regional estadual superior supremo
comarca vara varas juizado juizados turma turmas recursal camara camaras secao secoes
seccional secretaria cartorio foro gabinete presidencia presidente vice
corregedoria ouvidoria coordenacao coordenador assessoria nucleo central
defensoria publica uniao estado estados municipio municipios distrito
advocacia geral procuradoria procurador instituto nacional seguro social
previdencia previdenciario previdenciaria caixa economica banco brasil
receita fazenda universidade faculdade hospital hospitais clinica clinicas
laboratorio prefeitura municipal assembleia legislativa senado congresso
republica federativa governo conselho colegio ordem advogados seccional
conitec anvisa natjus nat jus sus ans cnes cfm crm coren orgao orgaos
entidade entidades autarquia fundacao empresa companhia sociedade
"""

#: Atos e peças processuais.
_PROCESSUAL = """
processo processos autos acao acoes peticao peticoes inicial contestacao
replica treplica impugnacao sentenca acordao acordaos despacho decisao
decisoes deliberacao recurso recursos apelacao agravo agravos embargos
declaracao mandado seguranca habeas corpus data liminar tutela antecipada
provisoria cautelar urgencia evidencia pedido pedidos uniformizacao
interpretacao divergencia incidente repetitivo repetitivos representativo
controversia paradigma sobrestamento admissibilidade inadmissao provimento
desprovimento improvimento reexame revolvimento prequestionamento
dispositivo tese teses fundamento fundamentos fundamentacao motivacao
merito preliminar preliminares prejudicial nulidade nulidades cerceamento
defesa contraditorio ampla devido legal processo julgado transito coisa
julgada execucao cumprimento liquidacao precatorio requisicao pequeno
valor pagamento honorarios sucumbencia custas gratuidade assistencia
judiciaria justica gratuita parecer manifestacao promocao cota
termo audiencia ata assentada conciliacao instrucao julgamento sessao
oficio memorial alegacoes finais razoes contrarrazoes intimacao citacao
notificacao relatorio voto ementa acordam vistos relatados discutidos
movimentacao evento eventos juntada certidao vista carga prazo preclusao
remessa baixa arquivamento desarquivamento distribuicao redistribuicao
procuracao substabelecimento mandato representacao
"""

#: Prova e convencimento.
_PROVA = """
prova provas probatorio probatoria conjunto elementos elemento tecnico
tecnicos tecnica tecnicas pericia pericial periciais perito laudo laudos
quesito quesitos testemunhal testemunho documental documentos documento
indicio indicios verossimilhanca convicao convencimento livre motivado
onus inversao presuncao fato fatos circunstancia circunstancias
hipossuficiencia suficiencia insuficiencia comprovacao comprovante
"""

#: Competência e via processual.
_COMPETENCIA = """
via vias eleita eleitas competencia competente incompetencia jurisdicao
jurisdicional instancia instancias grau graus alcada prevencao conexao
continencia litispendencia legitimidade ilegitimidade interesse agir
possibilidade juridica condicao condicoes pressuposto pressupostos
"""

#: Saúde, medicamentos e benefícios previdenciários.
_SAUDE = """
fornecimento fornecer medicamento medicamentos farmaco farmacos insumo
insumos tratamento tratamentos terapia terapias terapeutico terapeutica
terapeuticas incorporado incorporada incorporacao registro sanitario
protocolo protocolos clinico clinicas diretriz diretrizes evidencias
cientifica cientificas eficacia seguranca alternativa alternativas
prescricao prescrito receituario receita posologia dose dosagem
principio ativo cloridrato sulfato sodico dipropionato maleato besilato
bula generico similar referencia ampola comprimido comprimidos capsula
capsulas frasco seringa aplicacao mensal diaria continuo uso
beneficio beneficios auxilio auxilios aposentadoria pensao salario
maternidade doenca doencas incapacidade invalidez assistencial loas
prestacao continuada deficiencia impedimento longo prazo miserabilidade
renda familiar percapita capita grupo familiar
atestado prontuario exame exames diagnostico tratamento internacao
consulta encaminhamento relatorio medico medica saude
"""

#: Rótulos de documentos e identificadores (o rótulo, nunca o valor).
_ROTULOS = """
cpf cnpj identidade ssp sds detran denatran cnh nit pis pasep nis cep ddd
oab inss dpu dpe pgf pgu agu tjs trf stf stj tst tse tre cnj cid cids uf
cras creas aps der dib dcb pje eproc sei proc num obs fls doc docs anexo
anexos comprovante residencia extrato contracheque carteira trabalho
matricula registro cadastro requerimento protocolo sistema portal consulta
print tela imagem captura arquivo arquivos pagina paginas folha folhas
"""

#: Princípios ativos e marcas frequentes em litígio de saúde. Lista curta e
#: deliberadamente não exaustiva: a cobertura real vem dos sufixos
#: farmacológicos e do contexto ("medicamento X", "uso contínuo de X").
_FARMACOS = """
insulina glargina lispro degludeca aspart regular nph metformina glifage
dapagliflozina empagliflozina canagliflozina semaglutida liraglutida
dulaglutida tirzepatida ozempic victoza trulicity mounjaro saxenda
rivaroxabana apixabana dabigatrana edoxabana varfarina clopidogrel
enoxaparina heparina xarelto eliquis pradaxa
adalimumabe infliximabe etanercepte golimumabe certolizumabe tocilizumabe
rituximabe ustequinumabe secuquinumabe ixequizumabe risanquizumabe
dupilumabe omalizumabe mepolizumabe benralizumabe reslizumabe
humira remicade enbrel stelara cosentyx taltz skyrizi dupixent xolair
nusinersena risdiplam onasemnogeno zolgensma spinraza evrysdi
trastuzumabe pertuzumabe bevacizumabe cetuximabe panitumumabe nivolumabe
pembrolizumabe atezolizumabe durvalumabe ipilimumabe keytruda opdivo
imatinibe dasatinibe nilotinibe erlotinibe gefitinibe osimertinibe
ibrutinibe palbociclibe ribociclibe abemaciclibe olaparibe
sofosbuvir daclatasvir ledipasvir velpatasvir glecaprevir pibrentasvir
tenofovir lamivudina dolutegravir efavirenz zidovudina
duloxetina fluoxetina sertralina paroxetina citalopram escitalopram
venlafaxina desvenlafaxina bupropiona mirtazapina amitriptilina
nortriptilina clomipramina imipramina trazodona vortioxetina
pregabalina gabapentina carbamazepina oxcarbazepina lamotrigina
levetiracetam topiramato valproato divalproato fenitoina fenobarbital
clonazepam diazepam alprazolam lorazepam midazolam zolpidem
quetiapina olanzapina risperidona aripiprazol ziprasidona clozapina
haloperidol clorpromazina lurasidona paliperidona
omeprazol pantoprazol esomeprazol lansoprazol rabeprazol
losartana valsartana olmesartana candesartana telmisartana irbesartana
enalapril captopril ramipril lisinopril perindopril
anlodipino nifedipino verapamil diltiazem atenolol metoprolol
propranolol carvedilol bisoprolol nebivolol
sinvastatina atorvastatina rosuvastatina pravastatina ezetimiba
alirocumabe evolocumabe repatha praluent
levotiroxina metimazol propiltiouracil alendronato risedronato
denosumabe teriparatida prolia forteo
azitromicina amoxicilina ampicilina cefalexina ceftriaxona
ciprofloxacino levofloxacino moxifloxacino claritromicina clindamicina
vancomicina meropenem piperacilina tazobactam sulfametoxazol trimetoprima
prednisona prednisolona dexametasona hidrocortisona metilprednisolona
budesonida beclometasona fluticasona salbutamol formoterol salmeterol
tiotropio ipratropio montelucaste
dipirona paracetamol ibuprofeno diclofenaco nimesulida cetoprofeno
naproxeno meloxicam celecoxibe etoricoxibe tramadol codeina morfina
oxicodona metadona fentanil buprenorfina
ciclosporina tacrolimo micofenolato azatioprina metotrexato leflunomida
hidroxicloroquina sulfassalazina tofacitinibe baricitinibe upadacitinibe
canabidiol cannabidiol thc
"""

#: Vocabulário clínico. Nome de doença aparece em caixa de título com muita
#: frequência ("Doença Pulmonar Obstrutiva Crônica") e não identifica ninguém —
#: era tratado como nome de pessoa e redigido, estragando o texto.
_CLINICO = """
pulmonar pulmao cardiaca cardiaco cardiovascular renal hepatica hepatico
respiratoria respiratorio neurologica neurologico psiquiatrica psiquiatrico
gastrica gastrointestinal urinaria urologica ginecologica obstetrica
ortopedica oftalmologica otorrinolaringologica dermatologica endocrina
hematologica oncologica reumatologica imunologica infecciosa
obstrutiva restritiva cronica cronico aguda agudo severa severo grave
moderada leve progressiva degenerativa sistemica localizada generalizada
primaria secundaria terminal avancada incapacitante irreversivel
arterial venosa muscular ossea articular medular cerebral vascular
sindrome transtorno distúrbio disturbio patologia comorbidade sequela
sequelas lesao lesoes fratura fraturas insuficiencia hipertensao hipotensao
diabetes diabetico mellitus neoplasia neoplasico carcinoma tumor tumoral
metastase anemia leucemia linfoma esclerose artrite artrose osteoporose
depressao ansiedade esquizofrenia bipolar autismo epilepsia parkinson
alzheimer demencia avc infarto isquemia trombose embolia asma bronquite
enfisema fibrose cirrose hepatite nefropatia retinopatia neuropatia
cegueira surdez mobilidade reduzida amputacao paralisia paraplegia
tetraplegia hemiplegia deficit disfuncia disfuncao quadro clinico
diagnostico prognostico sintoma sintomas tratamento cirurgia cirurgico
internacao ambulatorial hospitalar emergencia urgencia
"""

#: Cargos, carreiras e vocabulário de concurso público. Aparecem em caixa de
#: título e em caixa alta o tempo todo ("AGENTE DE POLÍCIA FEDERAL") e não
#: identificam ninguém.
_CARGOS = """
agente agentes policia policial policiais delegado delegada escrivao escriva
inspetor inspetora papiloscopista comissario investigador carcereiro
militar militares soldado cabo sargento subtenente tenente capitao major
coronel brigadeiro almirante guarda bombeiro bombeiros vigilante
professor professora docente diretor diretora reitor coordenador chefe
enfermeiro enfermeira medico medica dentista odontologo farmaceutico
fisioterapeuta nutricionista psicologo psicologa assistente social
analista auditor auditora fiscal oficial auxiliar secretario secretaria
gerente supervisor administrador contador engenheiro engenheira arquiteto
tecnico tecnica operador motorista porteiro zelador faxineiro merendeira
cargo cargos carreira carreiras funcao funcoes emprego empregos
concurso concursos certame edital editais candidato candidata candidatos
vaga vagas posse nomeacao exoneracao aposentado aposentada pensionista
classificacao aprovacao aprovado aprovada reprovado reprovada eliminado
etapa etapas fase fases prova objetiva discursiva fisica psicotecnico
investigacao vida pregressa sindicancia idoneidade
"""

#: Rótulos de papel processual. Aparecem coladas ao nome ("REQUERENTE: FULANO")
#: e, em texto extraído de PDF, frequentemente na linha seguinte a um nome.
_PAPEIS = """
requerente requerentes requerido requeridos autor autora autores autoras
reu reus reclamante reclamado reclamantes reclamados impetrante impetrado
agravante agravado agravantes agravados recorrente recorrido recorrentes
recorridos embargante embargado exequente executado exequentes executados
suscitante suscitado apelante apelado apelantes apelados litisconsorte
assistido assistida assistidos interessado interessada interessados
testemunha testemunhas parte partes terceiro terceiros
procurador procuradora advogado advogada advogados defensor defensora
perito perita magistrado juiz juiza desembargador desembargadora ministro
ministra promotor promotora servidor servidora estagiario estagiaria
representante representado beneficiario beneficiaria dependente dependentes
titular titulares segurado segurada instituidor instituidora
"""

#: Estrutura do texto e expressões de redação forense.
_ESTRUTURA = """
assunto materia objeto causa pedir sintese resumo historico contexto
analise conclusao conclusoes consideracao consideracoes observacao
observacoes esclarecimento esclarecimentos informacao informacoes dado
dados resultado resultados situacao requisito requisitos criterio
criterios limite limites hipotese hipoteses caso casos questao questoes
introducao desenvolvimento ponto pontos item itens topico topicos
pessoas fisica fisicas natural naturais nome nomes denominacao razao
social fantasia sigla siglas
nos termos artigo artigos lei leis decreto portaria resolucao sumula
enunciado codigo civil penal processual trabalho consumidor tributario
administrativo constitucional constituicao emenda inciso incisos alinea
paragrafo paragrafos capitulo titulo livro secao anexo
excelentissimo excelentissima senhor senhora doutor doutora meritissimo
ilustrissimo dignissimo egregia colenda venerando
"""

#: Tempo e lugar.
_TEMPO_LUGAR = """
janeiro fevereiro marco abril maio junho julho agosto setembro outubro
novembro dezembro segunda terca quarta quinta sexta sabado domingo
hoje ontem amanha data hora horas dia dias mes meses ano anos
norte sul leste oeste centro brasilia minas gerais bahia parana catarina
goias espirito mato grosso amazonas ceara pernambuco maranhao piaui
alagoas sergipe paraiba rondonia acre roraima amapa tocantins
rua avenida travessa alameda praca rodovia estrada quadra bloco lote
conjunto setor bairro apartamento apto edificio residencial condominio
cidade municipio total reais real numero
"""

#: Palavras que, por si sós, afastam a hipótese de nome de pessoa.
TERMOS_NAO_PESSOA = _conjunto(
    "\n".join(
        (
            _INSTITUICOES,
            _PROCESSUAL,
            _PROVA,
            _COMPETENCIA,
            _SAUDE,
            _FARMACOS,
            _ROTULOS,
            _CLINICO,
            _CARGOS,
            _PAPEIS,
            _ESTRUTURA,
            _TEMPO_LUGAR,
        )
    )
)


# ---------------------------------------------------------------------------
# Evidência positiva: prenomes e sobrenomes usuais no Brasil.
# A lista não é exaustiva — nenhuma lista de nomes é. Ela serve para elevar a
# confiança, nunca para rejeitar sozinha um candidato em caixa de título.
# ---------------------------------------------------------------------------
_PRENOMES = """
joao jose antonio francisco carlos paulo pedro lucas luiz luis marcos gabriel
rafael daniel marcelo bruno eduardo felipe raimundo rodrigo manoel manuel
nelson roberto fabio alexandre jorge andre sergio ricardo fernando mario
sebastiao adriano leonardo gustavo julio cesar heitor arthur artur miguel
davi david bernardo theo lorenzo gael matheus mateus nicolas samuel enzo
joaquim benicio vicente caio diego thiago tiago vinicius wesley anderson
alan alex alisson erick emerson everton evandro renan renato rogerio
ronaldo valdir valter walter wagner washington wellington william willian
wilson claudio clovis cleber cristiano cristian denis douglas edson edilson
edgar edmilson eliseu elias elton fabiano fabricio flavio geraldo gilberto
gilmar giovani giovanni guilherme helio henrique hugo igor ivan jadson jair
jean jefferson joel jonas jonathan juliano kaio kevin leandro leonel levi
lincoln lucio marcio mauricio mauro michel michael milton moacir moises
murilo natanael nilton odair orlando oscar osmar osvaldo otavio patrick
ramon reginaldo reinaldo rene rian robson rodolfo romario romulo ruan rubens
rui saulo severino silas silvio simao sidney tadeu tarcisio tomas tulio
valdemar valentim vanderlei vitor victor waldir wanderson yago yuri ivo
benedito domingos lourenco afonso alberto aldo alfredo altair amauri anselmo
ari ariel armando arnaldo aroldo augusto aurelio bento bruno caetano camilo
celso cicero cleiton clemente custodio dalton danilo dario delmar
dirceu edmundo eduardo elison eliomar elmo emanuel ernesto euclides eugenio
ezequiel fabiano fausto felicio fernandes filipe firmino florencio francelino
frederico gelson genival geovane gerson gideon gilson gilvan givaldo
hamilton harrison hector hermes hilario horacio humberto iago idalberto
ilton ismael israel itamar ivanildo jacinto jaime jamil janio jarbas
jeronimo jesus joabe joanes jonatas jorge josue jucelino juvenal kleber
ladislau lauro lazaro lelio leobaldo lindomar lineu lucas lucio ludovico
luan marcelino marciano marcus marinho mariano marino martim martinho
matias maximiliano messias moacyr modesto natalino nereu nestor newton
nilo nivaldo noel norberto odilon olavo olimpio onofre osorio otacilio
ovidio pascoal paulino pericles plinio policarpo quirino rafaela raul
reynaldo ribamar rivaldo roberval rodolpho rolando romeu roni rosalvo
rubem salomao salvador sandro saturnino sebastian sidnei silvano simplicio
sinval sizenando tancredo teodoro teofilo tercio tobias ubaldo ubirajara
valdeci valdomiro valmir vanderley venancio vilmar virgilio vitorino
waldemar wanderlei wendel werner wesley wilton zacarias zeca zelito
maria ana francisca antonia adriana juliana marcia fernanda patricia aline
sandra camila amanda bruna jessica leticia julia luciana vanessa mariana
gabriela vera vitoria larissa claudia simone carla beatriz tatiane monica
andreia jaqueline silvia isabel priscila sonia rosa rosana roseli rute
raquel renata rita regina rejane rafaela nathalia natalia nayara neide
nilza noemi olivia paloma pamela paula paulina poliana rayane rebeca
sabrina samara sara sarah sheila silvana solange sueli suellen talita
tania tatiana telma teresa teresinha thais thaina valeria vania veronica
viviane wanda yasmin zilda alice helena laura manuela sophia sofia
isabella isabela luiza lorena livia heloisa mirella maite agatha giovanna
valentina cecilia eloa esther clara antonella isis emanuelly gabrielly
ayla elisa carolina caroline cristiane cristina daniela debora denise
diana edna elaine eliane elisabete elza emilia erica eva fabiana fatima
flavia gisele gislaine gloria graziela ines irene ivone janaina janete
joana josefa katia keila kelly lidia ligia lilian lucia lucimar luzia
magda marlene marly marta michele micheli miriam nadia neusa nubia
adelia adriane agda alba alcione alda alessandra alexandra alzira
amalia amelia angela angelica anita aparecida apolonia arlete augusta
aurea aurora benedita bernadete bianca branca bruna carmem carmen
cassia catarina celia celina cibele cidinha cilene cintia clarice
clelia conceicao consuelo cordelia dalva damaris darci delfina delma
dilma dinora dirce doralice dora dulce edileuza edileusa editte elenice
eliete elina elizabete eloisa elvira elza emanuela ercilia esmeralda
estela eunice euridice evelin fabiola fernanda filomena franciele
francielle gilda giselda gracinha guiomar hilda ilda iolanda iracema
irani iris irma isaura ivanilde ivete izabel jandira jeane joelma
jucilene julieta jurema laide laudicea leda leila lena leonor leticia
lia liana lidiane liliane lindalva lisete lourdes lucelia luciene
ludmila lurdes madalena mafalda maiara maisa malu manuella marcela
marcelle marcilene margarida margarete marialva maribel marileia
marilene marilia marines marisa marise maristela marize mercedes
micaela mirtes natercia nazare nelly nice nicole nilce nilda noelia
norma odete odila ofelia olga olinda onice ondina orlanda otilia
palmira pamella perola priscilla quiteria rachel ramona raimunda
regiane renilda rosalia rosangela rosaria roselene rosemary rosilene
rosimar rosimeire rosinha rozana ruth salete salome sebastiana selma
sidneia sirlei sirley sonia soraia soraya sueleni susana suzana
sylvia tamara tereza thamires thelma tiana tomasia valdeci valdira
valquiria vanda vania vera vilma vitalina wania wilma yara yolanda
zelia zenaide zenilda zilma zoraide zulmira
"""
PRENOMES = _conjunto(_PRENOMES)

_SOBRENOMES = """
silva santos oliveira souza sousa lima pereira ferreira alves rodrigues
costa gomes martins araujo melo mello barbosa ribeiro rocha carvalho
almeida lopes soares fernandes vieira monteiro cardoso reis moraes morais
moreira nunes marques machado freitas nascimento dias teixeira campos
borges miranda duarte castro andrade correia correa azevedo pinto
pinheiro ramos cavalcanti cavalcante cunha mendes batista braga sampaio
coelho farias siqueira tavares guimaraes magalhaes nogueira peixoto
prado queiroz quadros rangel sales salles santana saraiva xavier viana
vasconcelos aguiar amaral antunes assuncao bastos bezerra bittencourt
bonfim brandao bueno caldas camargo chaves cordeiro couto cruz esteves
fagundes falcao figueiredo fonseca fontes franca franco furtado galvao
godoy goncalves guedes macedo maciel maia mattos matos medeiros meireles
mesquita montenegro mota motta moura neves novaes paiva paes passos
pedrosa pessoa pontes porto rezende resende rios sa seixas serra sobral
toledo torres trindade valente valadares varela veloso ventura verissimo
vilela vargas wanderley zanetti abreu afonso aires albuquerque alencar
alencastro alvarenga alvares amorim anjos aranha arruda athayde avila
baptista baracho barreto barros basto belchior beltrao benevides bernardes
bezerril bitencourt boaventura bocaiuva bonifacio borba botelho brito
bulhoes burlamaqui caetano calado calmon camarao caminha canedo cantuaria
capanema carneiro carvalhaes cascais castelo castilho catao cerqueira
chagas chermont coimbra colares conceicao cordovil cortez crisostomo
cruzeiro dantas delgado dorneles drummond dutra eiras escobar espindola
estrela euzebio faria feijo feitosa felicio fialho fidelis figueira filgueiras
flores floriano fogaca formiga fortes fraga frazao freire frota gadelha
gentil geraldo girao goes gondim gouveia gurgel holanda hora jacome jardim
jucá junqueira juruena lacerda lamego landim lavor leal leitao leite lemos
lins lobato lobo lousada lucena luz macena machadinho madeira magno maranhao
marinho marinho marreiros martinho matta mattoso mauricio mayer meira mello
meneses menezes mesquita milanez mindello mola moniz montes morato mourao
muniz murta nazare negreiros nepomuceno neri neto nobre noronha oliva
pacheco padilha padua paim paixao pamplona pantoja parente pastana pedroso
penha pequeno peralta perdigao pergentino pessanha philippe picanco pimentel
pinheiros pires pitanga pombo portela portugal pousada povoas prazeres
proenca quaresma quental rabelo rabello raposo rebouças regis renault
ribas ricardo rodovalho rolim romao rosado roriz sabino saldanha salgado
sales salustiano sancho sandoval sarmento sayao schmidt sepulveda sertao
sette sever severo sigueira simas simoes soledade solon sorrentino sotero
sucupira tamandare tapajos tarquino tenorio terra tinoco tolentino tomaz
tourinho trajano travassos tupinamba ururahy vale valim valle vanderley
vaz veiga vergara viegas vilaca vilanova vilar vilhena vital viveiros
wagner werneck westphalen whitaker xerez zacarias zagallo zuzarte
"""
SOBRENOMES = _conjunto(_SOBRENOMES)

# ---------------------------------------------------------------------------
# Localidades. Um estado ou município pode identificar a pessoa e por isso é
# detectado — mas é **lugar**, não pessoa: não recebe papel processual nem
# pseudônimo de parte. "REQUERIDO: ESTADO DE SANTA CATARINA" tem como requerido
# o Estado, e não a localidade; chamar "Santa Catarina" de [REQUERIDO_1] está
# errado nos dois sentidos.
# ---------------------------------------------------------------------------
_UNIDADES_FEDERATIVAS = """
acre alagoas amapa amazonas bahia ceara espirito-santo goias maranhao
mato-grosso mato-grosso-do-sul minas-gerais para paraiba parana pernambuco
piaui rio-de-janeiro rio-grande-do-norte rio-grande-do-sul rondonia roraima
santa-catarina sao-paulo sergipe tocantins distrito-federal
"""

_CAPITAIS = """
rio-branco maceio macapa manaus salvador fortaleza brasilia vitoria goiania
sao-luis cuiaba campo-grande belo-horizonte belem joao-pessoa curitiba recife
teresina natal porto-alegre porto-velho boa-vista florianopolis aracaju palmas
"""


def _conjunto_de_expressoes(bruto: str) -> frozenset[str]:
    """Expressões de várias palavras, escritas com hífen no lugar do espaço."""
    return frozenset(
        normalizar(t).replace("-", " ") for t in bruto.split() if len(t) > 1
    )


#: Nomes de unidade federativa e capital, para reconhecer a localidade mesmo
#: sem rótulo ("Turma Recursal de Santa Catarina").
LOCALIDADES_CONHECIDAS = _conjunto_de_expressoes(
    _UNIDADES_FEDERATIVAS
) | _conjunto_de_expressoes(_CAPITAIS)

#: Expressões que, imediatamente antes, indicam que o que vem a seguir é um
#: lugar — e não uma pessoa.
ROTULOS_LOCALIDADE = (
    "estado de",
    "estado do",
    "estado da",
    "municipio de",
    "municipio do",
    "municipio da",
    "comarca de",
    "comarca do",
    "comarca da",
    "cidade de",
    "cidade do",
    "cidade da",
    "secao judiciaria de",
    "secao judiciaria do",
    "subsecao judiciaria de",
    "turma recursal de",
    "turma recursal do",
    "tribunal de justica de",
    "tribunal de justica do",
    "tribunal regional federal de",
    "natural de",
    "nascido em",
    "nascida em",
    "residente em",
    "domiciliado em",
    "domiciliada em",
    "foro de",
    "vara de",
    "regiao de",
)


def e_localidade(candidato: str) -> bool:
    """O candidato, inteiro ou no fim, é uma localidade conhecida?"""
    normal = normalizar(candidato).strip(".,;:()")
    if normal in LOCALIDADES_CONHECIDAS:
        return True
    return any(normal.endswith(" " + local) for local in LOCALIDADES_CONHECIDAS)


#: Qualquer token conhecido como parte de nome de pessoa.
NOMES_CONHECIDOS = PRENOMES | SOBRENOMES

#: Conectores aceitos dentro de um nome composto.
CONECTORES_NOME = frozenset({"de", "da", "do", "das", "dos", "e", "del", "van", "von", "d'"})


#: Sufixos de denominação comum de medicamento (padrão da OMS para
#: denominações genéricas). Só entram os que não colidem com nomes de pessoa:
#: ``-ina`` e ``-ol``, por exemplo, ficam de fora, porque gerariam falso
#: negativo em "Marina", "Carolina", "Nicole".
SUFIXOS_FARMACO = (
    "mabe",
    "umabe",
    "ximabe",
    "zumabe",
    "cepte",
    "nibe",
    "tinibe",
    "ciclibe",
    "paribe",
    "prazol",
    "sartana",
    "statina",
    "vastatina",
    "ciclina",
    "micina",
    "cilina",
    "floxacino",
    "oxetina",
    "gliptina",
    "glifozina",
    "gliflozina",
    "glutida",
    "xabana",
    "parina",
    "azepam",
    "zepam",
    "fenaco",
    "profeno",
    "pridona",
    "piprazol",
    "apina",
    "triptano",
    "setrona",
    "dipino",
    "olol",
    "pril",
    "dronato",
    "tidina",
    "virina",
    "navir",
    "ciclovir",
    "tegravir",
)


def parece_farmaco(token: str) -> bool:
    """O token tem forma de denominação de medicamento?

    Um token que também é nome conhecido nunca é tratado como medicamento.
    """
    normal = normalizar(token).strip(".,;:()")
    if normal in NOMES_CONHECIDOS or len(normal) < 6:
        return False
    return normal.endswith(SUFIXOS_FARMACO)


def e_termo_de_pessoa(token: str) -> bool:
    """O token é um prenome ou sobrenome conhecido?"""
    return normalizar(token).strip(".,;:()") in NOMES_CONHECIDOS


def e_vocabulario_comum(token: str) -> bool:
    """O token é vocabulário que não identifica pessoa?

    Um token que também é nome conhecido (``Campos``, ``Serra``, ``Pessoa``)
    nunca é tratado como vocabulário comum, para não descartar nomes reais.
    """
    normal = normalizar(token).strip(".,;:()")
    if normal in NOMES_CONHECIDOS:
        return False
    if normal in TERMOS_NAO_PESSOA or normal in PALAVRAS_FUNCIONAIS:
        return True
    return parece_farmaco(token)
