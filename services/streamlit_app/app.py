import streamlit as st
import requests
from datetime import datetime
import plotly.graph_objects as go

# Configure the page
st.set_page_config(
    page_title="Sistema de Crédito Rural",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# App title and description
st.title("🌾 Sistema de Análise de Crédito Rural")
st.markdown("""
Esta aplicação permite consultar o score de crédito rural de um proponente através de um modelo de Machine Learning.
Preencha os dados do produtor rural e da propriedade abaixo e clique em **Verificar Solicitação** para obter o resultado.
""")

# API Configuration
API_BASE_URL = "http://credit-scoring-api:8000"
SCORE_ENDPOINT = f"{API_BASE_URL}/score"
HEALTH_ENDPOINT = f"{API_BASE_URL}/health"

def check_api_health():
    """Check if the API is healthy"""
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        return response.status_code == 200
    except:
        return False

def call_scoring_api(payload):
    """Call the scoring API with the provided payload"""
    try:
        response = requests.post(
            SCORE_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json(), None
        else:
            return None, f"Erro na API: {response.status_code} - {response.text}"
    except requests.exceptions.RequestException as e:
        return None, f"Erro de conexão: {str(e)}"

def validate_cpf_cnpj(cpf_cnpj):
    """Basic CPF/CNPJ validation"""
    if not cpf_cnpj:
        return False
    
    # Remove formatting
    clean_doc = ''.join(filter(str.isdigit, cpf_cnpj))
    
    # Check if it's CPF (11 digits) or CNPJ (14 digits)
    if len(clean_doc) == 11:
        return True  # CPF
    elif len(clean_doc) == 14:
        return True  # CNPJ
    else:
        return False

def display_score_result(result):
    """Display the scoring result in a formatted way"""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Score de Crédito", f"{result['score']:.2f}")
    
    with col2:
        risk_colors = {
            "low": "🟢",
            "medium": "🟡", 
            "high": "🔴"
        }
        risk_labels = {
            "low": "Baixo Risco",
            "medium": "Médio Risco",
            "high": "Alto Risco"
        }
        
        risk_category = result.get('risk_category', 'unknown')
        risk_icon = risk_colors.get(risk_category, "⚪")
        risk_label = risk_labels.get(risk_category, "Desconhecido")
        
        st.metric("Categoria de Risco", f"{risk_icon} {risk_label}")
    
    with col3:
        approval_status = "✅ APROVADO" if result['score'] >= 0.6 else "❌ NEGADO"
        approval_color = "green" if result['score'] >= 0.6 else "red"
        st.markdown(f"**Status:** :{approval_color}[{approval_status}]")
    
    # Score gauge chart
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = result['score'],
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Score de Crédito"},
        gauge = {
            'axis': {'range': [None, 1]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 0.4], 'color': "red"},
                {'range': [0.4, 0.7], 'color': "yellow"},
                {'range': [0.7, 1], 'color': "green"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 0.6
            }
        }
    ))
    
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)
    
    # Explanation
    st.subheader("📋 Explicação do Resultado")
    st.info(result.get('explanation', 'Nenhuma explicação disponível'))

def main():
    # Check API health
    if not check_api_health():
        st.error("⚠️ API de scoring não está disponível. Verifique se o serviço está rodando.")
        st.stop()
    
    # Success message for API
    st.success("✅ API de scoring está funcionando corretamente")
    
    # Create form
    with st.form("credit_scoring_form"):
        st.subheader("📝 Dados do Proponente")
        
        # Personal/Business information
        col1, col2 = st.columns(2)
        
        with col1:
            proponente_id = st.text_input(
                "ID do Proponente",
                placeholder="Ex: PROP_001",
                help="Identificador único do proponente"
            )
            
            cpf_cnpj = st.text_input(
                "CPF/CNPJ",
                placeholder="000.000.000-00 ou 00.000.000/0000-00",
                help="CPF para pessoa física ou CNPJ para pessoa jurídica"
            )
            
            nome_razao_social = st.text_input(
                "Nome/Razão Social",
                placeholder="Nome completo ou razão social",
                help="Nome da pessoa física ou razão social da empresa"
            )
            
            tipo_pessoa = st.selectbox(
                "Tipo de Pessoa",
                options=["FISICA", "JURIDICA"],
                help="Tipo de pessoa: física ou jurídica"
            )
            
            renda_bruta_anual = st.number_input(
                "Renda Bruta Anual (R$)",
                min_value=0.0,
                value=120000.0,
                step=1000.0,
                help="Renda bruta anual declarada"
            )
            
            valor_solicitado = st.number_input(
                "Valor Solicitado (R$)",
                min_value=1000.0,
                value=80000.0,
                step=1000.0,
                help="Valor do crédito solicitado"
            )
            
            finalidade_credito = st.selectbox(
                "Finalidade do Crédito",
                options=["CUSTEIO_SAFRA", "INVESTIMENTO_MAQUINARIO", "AMPLIACAO_AREA", "REFORMA_INSTALACOES"],
                format_func=lambda x: {
                    "CUSTEIO_SAFRA": "Custeio de Safra",
                    "INVESTIMENTO_MAQUINARIO": "Investimento em Maquinário",
                    "AMPLIACAO_AREA": "Ampliação de Área",
                    "REFORMA_INSTALACOES": "Reforma de Instalações"
                }.get(x, x),
                help="Finalidade do crédito rural"
            )
        
        with col2:
            st.subheader("🏞️ Dados da Propriedade")
            
            area_total_hectares = st.number_input(
                "Área Total (hectares)",
                min_value=0.1,
                value=50.0,
                step=0.1,
                help="Área total da propriedade em hectares"
            )
            
            cultura_principal = st.selectbox(
                "Cultura Principal",
                options=["SOJA", "CAFE", "MILHO", "FRUTICULTURA", "PECUARIA", "CANA_ACUCAR"],
                format_func=lambda x: {
                    "SOJA": "Soja",
                    "CAFE": "Café",
                    "MILHO": "Milho",
                    "FRUTICULTURA": "Fruticultura",
                    "PECUARIA": "Pecuária",
                    "CANA_ACUCAR": "Cana-de-açúcar"
                }.get(x, x),
                help="Principal cultura da propriedade"
            )
            
            possui_experiencia = st.selectbox(
                "Possui Experiência na Atividade?",
                options=[True, False],
                format_func=lambda x: "Sim" if x else "Não",
                help="Possui experiência na atividade rural?"
            )
            
            anos_experiencia = st.number_input(
                "Anos de Experiência",
                min_value=0,
                max_value=50,
                value=8,
                help="Anos de experiência na atividade rural"
            )
            
            # Location data
            st.subheader("📍 Localização")
            
            municipio = st.text_input(
                "Município",
                placeholder="Ex: Campo Grande",
                help="Município da propriedade"
            )
            
            uf = st.selectbox(
                "UF",
                options=["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"],
                help="Estado da propriedade"
            )
            
            # Additional data
            st.subheader("📊 Dados Adicionais")
            
            serasa_score = st.number_input(
                "Serasa Score",
                min_value=0,
                max_value=1000,
                value=620,
                help="Score do Serasa"
            )
            
            ibama_autuacoes = st.selectbox(
                "Autuações IBAMA Ativas?",
                options=[False, True],
                format_func=lambda x: "Sim" if x else "Não",
                help="Possui autuações ativas no IBAMA?"
            )
            
            numero_matricula = st.text_input(
                "Número da Matrícula do Imóvel",
                placeholder="Ex: MAT-620456",
                help="Número da matrícula do imóvel rural"
            )
        
        # Submit button
        submitted = st.form_submit_button("🔍 Verificar Solicitação", use_container_width=True)
        
        if submitted:
            # Validate required fields
            if not proponente_id:
                st.error("❌ ID do Proponente é obrigatório.")
                return
            
            if not validate_cpf_cnpj(cpf_cnpj):
                st.error("❌ CPF/CNPJ inválido. Digite um CPF (11 dígitos) ou CNPJ (14 dígitos) válido.")
                return
            
            if not nome_razao_social:
                st.error("❌ Nome/Razão Social é obrigatório.")
                return
            
            if not municipio:
                st.error("❌ Município é obrigatório.")
                return
            
            if not numero_matricula:
                st.error("❌ Número da Matrícula do Imóvel é obrigatório.")
                return
            
            # Prepare payload according to API structure
            payload = {
                "proponente_id": proponente_id,
                "data_solicitacao": int(datetime.now().timestamp() * 1000),  # Current timestamp in milliseconds
                "cpf_cnpj": cpf_cnpj,
                "nome_razao_social": nome_razao_social,
                "tipo_pessoa": tipo_pessoa,
                "renda_bruta_anual_declarada": renda_bruta_anual,
                "valor_solicitado_credito": valor_solicitado,
                "finalidade_credito": finalidade_credito,
                "localizacao_propriedade": {
                    "latitude": -22.9068,  # Default coordinates (can be enhanced later)
                    "longitude": -43.1729,
                    "municipio": municipio,
                    "uf": uf
                },
                "area_total_hectares": area_total_hectares,
                "cultura_principal": cultura_principal,
                "possui_experiencia_atividade": possui_experiencia,
                "anos_experiencia": anos_experiencia,
                "fontes_dados_adicionais": {
                    "serasa_score": serasa_score,
                    "ibama_autuacoes_ativas": ibama_autuacoes,
                    "numero_matricula_imovel": numero_matricula
                },
                "metadata_evento": {
                    "versao_schema": "1.0.0",
                    "origem_dados": "streamlit_webapp",
                    "timestamp_geracao_evento": int(datetime.now().timestamp() * 1000)
                }
            }
            
            # Show payload in sidebar (for debugging)
            with st.sidebar:
                st.subheader("📋 Dados Enviados")
                st.json(payload)
            
            # Call API
            with st.spinner("Processando solicitação..."):
                result, error = call_scoring_api(payload)
            
            if error:
                st.error(f"❌ Erro ao processar solicitação: {error}")
            else:
                st.success("✅ Solicitação processada com sucesso!")
                
                # Display results
                display_score_result(result)
                
                # Show full response in sidebar
                with st.sidebar:
                    st.subheader("📊 Resposta Completa")
                    st.json(result)
    
    # Footer
    st.markdown("---")
    st.markdown(
        "**Sistema de Análise de Crédito Rural** - Powered by Matheus Damasceno | "
        f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )

if __name__ == "__main__":
    main()