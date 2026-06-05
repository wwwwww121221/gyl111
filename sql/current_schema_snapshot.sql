--
-- PostgreSQL database dump
--

\restrict YlqtNaUoriPlrZfMAEccDFxeqluaeuELJ39LPKT8z9ApccflVQxsSamtvVPg0vn

-- Dumped from database version 18.3
-- Dumped by pg_dump version 18.3

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

-- *not* creating schema, since initdb creates it


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS '';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: assessment_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assessment_items (
    id integer NOT NULL,
    dimension character varying NOT NULL,
    dimension_weight double precision NOT NULL,
    indicator character varying NOT NULL,
    max_score double precision NOT NULL,
    scoring_department character varying NOT NULL,
    sort_order integer
);


--
-- Name: COLUMN assessment_items.dimension; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assessment_items.dimension IS '大维度名称';


--
-- Name: COLUMN assessment_items.dimension_weight; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assessment_items.dimension_weight IS '大维度权重(如0.3表示30%)';


--
-- Name: COLUMN assessment_items.indicator; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assessment_items.indicator IS '小维度/核心考核指标';


--
-- Name: COLUMN assessment_items.max_score; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assessment_items.max_score IS '该项满分';


--
-- Name: COLUMN assessment_items.scoring_department; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assessment_items.scoring_department IS '负责打分的部门';


--
-- Name: COLUMN assessment_items.sort_order; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assessment_items.sort_order IS '排序序号';


--
-- Name: assessment_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assessment_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assessment_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assessment_items_id_seq OWNED BY public.assessment_items.id;


--
-- Name: assessment_supplier_scores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assessment_supplier_scores (
    id integer NOT NULL,
    task_id integer NOT NULL,
    supplier_id integer NOT NULL,
    item_id integer NOT NULL,
    score double precision,
    remark text,
    scored_by integer,
    scored_at timestamp without time zone
);


--
-- Name: COLUMN assessment_supplier_scores.score; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assessment_supplier_scores.score IS '打分(可为空表示未打)';


--
-- Name: COLUMN assessment_supplier_scores.remark; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assessment_supplier_scores.remark IS '打分备注';


--
-- Name: COLUMN assessment_supplier_scores.scored_by; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assessment_supplier_scores.scored_by IS '打分人';


--
-- Name: COLUMN assessment_supplier_scores.scored_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assessment_supplier_scores.scored_at IS '打分时间';


--
-- Name: assessment_supplier_scores_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assessment_supplier_scores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assessment_supplier_scores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assessment_supplier_scores_id_seq OWNED BY public.assessment_supplier_scores.id;


--
-- Name: assessment_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assessment_tasks (
    id integer NOT NULL,
    name character varying NOT NULL,
    assessment_type character varying NOT NULL,
    status character varying,
    scoring_start timestamp without time zone NOT NULL,
    scoring_end timestamp without time zone NOT NULL,
    description text,
    created_by integer,
    created_at timestamp without time zone,
    completed_at timestamp without time zone,
    scorers json
);


--
-- Name: COLUMN assessment_tasks.name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assessment_tasks.name IS '考核名称';


--
-- Name: COLUMN assessment_tasks.assessment_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assessment_tasks.assessment_type IS '考核类型: annual/quarterly/special';


--
-- Name: COLUMN assessment_tasks.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assessment_tasks.status IS 'scoring/summary/completed';


--
-- Name: COLUMN assessment_tasks.scoring_start; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assessment_tasks.scoring_start IS '打分开始时间';


--
-- Name: COLUMN assessment_tasks.scoring_end; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assessment_tasks.scoring_end IS '打分截止时间';


--
-- Name: COLUMN assessment_tasks.description; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assessment_tasks.description IS '考核说明';


--
-- Name: assessment_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assessment_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assessment_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assessment_tasks_id_seq OWNED BY public.assessment_tasks.id;


--
-- Name: compare_drafts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.compare_drafts (
    id integer NOT NULL,
    task_id integer NOT NULL,
    buyer_id integer NOT NULL,
    task_title character varying,
    material_code character varying NOT NULL,
    material_name character varying,
    supplier_count integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: compare_drafts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.compare_drafts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: compare_drafts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.compare_drafts_id_seq OWNED BY public.compare_drafts.id;


--
-- Name: contract_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contract_templates (
    id integer NOT NULL,
    name character varying NOT NULL,
    file_path character varying NOT NULL,
    default_buyer_name character varying,
    is_active boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: contract_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contract_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contract_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contract_templates_id_seq OWNED BY public.contract_templates.id;


--
-- Name: contracts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contracts (
    id integer NOT NULL,
    task_id integer NOT NULL,
    inquiry_supplier_id integer NOT NULL,
    pdf_path text,
    status character varying,
    generated_by integer,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    total_amount double precision,
    buyer_company_name character varying,
    history_versions json,
    address character varying,
    legal_representative character varying,
    agent character varying,
    contact_phone character varying,
    bank_name character varying,
    bank_account character varying,
    tax_id character varying,
    fax character varying,
    postal_code character varying,
    template_id integer,
    template_name character varying,
    template_file_path character varying
);


--
-- Name: contracts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contracts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contracts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contracts_id_seq OWNED BY public.contracts.id;


--
-- Name: inquiry_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inquiry_requests (
    id integer NOT NULL,
    erp_request_id character varying,
    bill_no character varying,
    project_info json,
    material_code character varying,
    material_name character varying,
    qty double precision,
    target_price double precision,
    delivery_date timestamp without time zone,
    status character varying,
    created_at timestamp without time zone,
    material_model character varying,
    price_unit_name character varying
);


--
-- Name: COLUMN inquiry_requests.erp_request_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inquiry_requests.erp_request_id IS 'ERP采购申请单号+行号';


--
-- Name: COLUMN inquiry_requests.bill_no; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inquiry_requests.bill_no IS 'ERP单据编号';


--
-- Name: COLUMN inquiry_requests.project_info; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inquiry_requests.project_info IS '项目信息 {number, name}';


--
-- Name: COLUMN inquiry_requests.target_price; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inquiry_requests.target_price IS '期望单价';


--
-- Name: inquiry_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.inquiry_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: inquiry_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.inquiry_requests_id_seq OWNED BY public.inquiry_requests.id;


--
-- Name: inquiry_suppliers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inquiry_suppliers (
    id integer NOT NULL,
    task_id integer,
    supplier_id integer,
    current_round integer,
    status character varying,
    latest_ai_feedback text,
    created_at timestamp without time zone,
    allocated_ratio double precision,
    allocated_qty double precision,
    item_allocations json
);


--
-- Name: COLUMN inquiry_suppliers.latest_ai_feedback; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inquiry_suppliers.latest_ai_feedback IS '最新的AI谈判反馈';


--
-- Name: inquiry_suppliers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.inquiry_suppliers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: inquiry_suppliers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.inquiry_suppliers_id_seq OWNED BY public.inquiry_suppliers.id;


--
-- Name: inquiry_task_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inquiry_task_items (
    id integer NOT NULL,
    task_id integer,
    request_id integer
);


--
-- Name: inquiry_task_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.inquiry_task_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: inquiry_task_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.inquiry_task_items_id_seq OWNED BY public.inquiry_task_items.id;


--
-- Name: inquiry_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inquiry_tasks (
    id integer NOT NULL,
    title character varying NOT NULL,
    strategy_config json,
    status character varying,
    created_by integer,
    created_at timestamp without time zone,
    deadline timestamp without time zone,
    type character varying DEFAULT 'auto'::character varying,
    buyer_id integer,
    approved_by integer,
    approved_at timestamp without time zone,
    approval_comment text
);


--
-- Name: COLUMN inquiry_tasks.strategy_config; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.inquiry_tasks.strategy_config IS '谈判策略配置 {max_rounds, bargain_ratio...}';


--
-- Name: inquiry_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.inquiry_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: inquiry_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.inquiry_tasks_id_seq OWNED BY public.inquiry_tasks.id;


--
-- Name: materials; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.materials (
    id integer NOT NULL,
    code character varying NOT NULL,
    name character varying NOT NULL,
    specification character varying,
    erp_cls_id character varying,
    group_name character varying,
    base_unit character varying,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: COLUMN materials.code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.materials.code IS '物料编码';


--
-- Name: COLUMN materials.name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.materials.name IS '物料名称';


--
-- Name: COLUMN materials.specification; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.materials.specification IS '规格型号';


--
-- Name: COLUMN materials.erp_cls_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.materials.erp_cls_id IS '物料属性(1外购, 2自制, 10资产, 11费用, 6服务)';


--
-- Name: COLUMN materials.group_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.materials.group_name IS '物料分组';


--
-- Name: COLUMN materials.base_unit; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.materials.base_unit IS '基本单位';


--
-- Name: materials_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.materials_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: materials_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.materials_id_seq OWNED BY public.materials.id;


--
-- Name: operation_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.operation_logs (
    id integer NOT NULL,
    user_id integer,
    action_type character varying NOT NULL,
    detail character varying,
    ip_address character varying,
    created_at timestamp without time zone,
    module character varying,
    target_type character varying,
    target_name character varying,
    result character varying DEFAULT 'success'::character varying,
    extra_data json
);


--
-- Name: COLUMN operation_logs.action_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.operation_logs.action_type IS 'LOGIN, CREATE_USER, DELETE_USER, APPROVE_SUPPLIER, CREATE_INQUIRY, SEND_WARNING';


--
-- Name: operation_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.operation_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: operation_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.operation_logs_id_seq OWNED BY public.operation_logs.id;


--
-- Name: purchase_order_monthly_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.purchase_order_monthly_stats (
    id integer NOT NULL,
    supplier_code character varying NOT NULL,
    supplier_name character varying,
    material_code character varying NOT NULL,
    material_name character varying,
    stat_month timestamp without time zone NOT NULL,
    order_count integer,
    total_qty double precision,
    total_amount double precision,
    avg_tax_net_price double precision,
    min_tax_net_price double precision,
    max_tax_net_price double precision,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: purchase_order_monthly_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.purchase_order_monthly_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: purchase_order_monthly_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.purchase_order_monthly_stats_id_seq OWNED BY public.purchase_order_monthly_stats.id;


--
-- Name: purchase_order_summary; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.purchase_order_summary (
    id integer NOT NULL,
    supplier_code character varying NOT NULL,
    supplier_name character varying,
    material_code character varying NOT NULL,
    material_name character varying,
    order_count integer,
    total_qty double precision,
    total_amount double precision,
    avg_price double precision,
    avg_tax_net_price double precision,
    latest_price double precision,
    latest_tax_net_price double precision,
    latest_date timestamp without time zone,
    lowest_price double precision,
    lowest_date timestamp without time zone,
    highest_price double precision,
    highest_date timestamp without time zone,
    avg_30_days double precision,
    recent_order_count integer,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: purchase_order_summary_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.purchase_order_summary_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: purchase_order_summary_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.purchase_order_summary_id_seq OWNED BY public.purchase_order_summary.id;


--
-- Name: quotations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quotations (
    id integer NOT NULL,
    inquiry_supplier_id integer,
    round integer NOT NULL,
    item_id integer,
    qty double precision,
    price double precision NOT NULL,
    delivery_date timestamp without time zone,
    remark text,
    ai_analysis json,
    created_at timestamp without time zone
);


--
-- Name: COLUMN quotations.qty; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.quotations.qty IS '供应商可供数量';


--
-- Name: COLUMN quotations.ai_analysis; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.quotations.ai_analysis IS 'AI分析结果';


--
-- Name: quotations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.quotations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: quotations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.quotations_id_seq OWNED BY public.quotations.id;


--
-- Name: supplier_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.supplier_members (
    id integer NOT NULL,
    supplier_id integer NOT NULL,
    user_id integer NOT NULL,
    role character varying,
    status character varying,
    member_name character varying,
    "position" character varying,
    application_note text,
    application_attachments json,
    approval_mode character varying,
    reviewed_by integer,
    reviewed_at timestamp without time zone,
    review_comment text,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: COLUMN supplier_members.role; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.supplier_members.role IS 'owner/admin/member';


--
-- Name: COLUMN supplier_members.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.supplier_members.status IS 'pending/active/rejected/disabled';


--
-- Name: COLUMN supplier_members.approval_mode; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.supplier_members.approval_mode IS 'platform_admin/supplier_admin';


--
-- Name: supplier_members_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.supplier_members_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: supplier_members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.supplier_members_id_seq OWNED BY public.supplier_members.id;


--
-- Name: supplier_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.supplier_metrics (
    id integer NOT NULL,
    supplier_id integer,
    task_id integer,
    response_time_minutes integer,
    total_rounds integer,
    final_deal_rate double precision,
    price_competitiveness double precision,
    created_at timestamp without time zone
);


--
-- Name: supplier_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.supplier_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: supplier_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.supplier_metrics_id_seq OWNED BY public.supplier_metrics.id;


--
-- Name: suppliers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.suppliers (
    id integer NOT NULL,
    name character varying,
    contact_person character varying,
    phone character varying,
    email character varying,
    level character varying,
    status character varying,
    user_id integer,
    rating_score double precision,
    code character varying,
    short_name character varying,
    group_name character varying,
    grade character varying,
    reviewer_id integer,
    reviewed_at timestamp without time zone,
    social_credit_code character varying,
    application_attachments json,
    onboarding_note text,
    review_comment text,
    profile_audit_status character varying DEFAULT 'draft'::character varying,
    pending_profile_update json
);


--
-- Name: COLUMN suppliers.level; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.suppliers.level IS 'general/core';


--
-- Name: COLUMN suppliers.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.suppliers.status IS 'pending/approved/rejected';


--
-- Name: suppliers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.suppliers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: suppliers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.suppliers_id_seq OWNED BY public.suppliers.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying NOT NULL,
    password_hash character varying NOT NULL,
    role character varying,
    created_at timestamp without time zone,
    department character varying,
    phone character varying,
    openid character varying
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: warning_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.warning_messages (
    id integer NOT NULL,
    supplier_id integer,
    content text NOT NULL,
    created_at timestamp without time zone,
    is_read boolean,
    buyer_id integer,
    read_at timestamp without time zone,
    supplier_remark text
);


--
-- Name: warning_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.warning_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: warning_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.warning_messages_id_seq OWNED BY public.warning_messages.id;


--
-- Name: assessment_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_items ALTER COLUMN id SET DEFAULT nextval('public.assessment_items_id_seq'::regclass);


--
-- Name: assessment_supplier_scores id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_supplier_scores ALTER COLUMN id SET DEFAULT nextval('public.assessment_supplier_scores_id_seq'::regclass);


--
-- Name: assessment_tasks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_tasks ALTER COLUMN id SET DEFAULT nextval('public.assessment_tasks_id_seq'::regclass);


--
-- Name: compare_drafts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compare_drafts ALTER COLUMN id SET DEFAULT nextval('public.compare_drafts_id_seq'::regclass);


--
-- Name: contract_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contract_templates ALTER COLUMN id SET DEFAULT nextval('public.contract_templates_id_seq'::regclass);


--
-- Name: contracts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts ALTER COLUMN id SET DEFAULT nextval('public.contracts_id_seq'::regclass);


--
-- Name: inquiry_requests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inquiry_requests ALTER COLUMN id SET DEFAULT nextval('public.inquiry_requests_id_seq'::regclass);


--
-- Name: inquiry_suppliers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inquiry_suppliers ALTER COLUMN id SET DEFAULT nextval('public.inquiry_suppliers_id_seq'::regclass);


--
-- Name: inquiry_task_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inquiry_task_items ALTER COLUMN id SET DEFAULT nextval('public.inquiry_task_items_id_seq'::regclass);


--
-- Name: inquiry_tasks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inquiry_tasks ALTER COLUMN id SET DEFAULT nextval('public.inquiry_tasks_id_seq'::regclass);


--
-- Name: materials id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.materials ALTER COLUMN id SET DEFAULT nextval('public.materials_id_seq'::regclass);


--
-- Name: operation_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operation_logs ALTER COLUMN id SET DEFAULT nextval('public.operation_logs_id_seq'::regclass);


--
-- Name: purchase_order_monthly_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_monthly_stats ALTER COLUMN id SET DEFAULT nextval('public.purchase_order_monthly_stats_id_seq'::regclass);


--
-- Name: purchase_order_summary id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_summary ALTER COLUMN id SET DEFAULT nextval('public.purchase_order_summary_id_seq'::regclass);


--
-- Name: quotations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quotations ALTER COLUMN id SET DEFAULT nextval('public.quotations_id_seq'::regclass);


--
-- Name: supplier_members id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_members ALTER COLUMN id SET DEFAULT nextval('public.supplier_members_id_seq'::regclass);


--
-- Name: supplier_metrics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_metrics ALTER COLUMN id SET DEFAULT nextval('public.supplier_metrics_id_seq'::regclass);


--
-- Name: suppliers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suppliers ALTER COLUMN id SET DEFAULT nextval('public.suppliers_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: warning_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.warning_messages ALTER COLUMN id SET DEFAULT nextval('public.warning_messages_id_seq'::regclass);


--
-- Name: assessment_items assessment_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_items
    ADD CONSTRAINT assessment_items_pkey PRIMARY KEY (id);


--
-- Name: assessment_supplier_scores assessment_supplier_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_supplier_scores
    ADD CONSTRAINT assessment_supplier_scores_pkey PRIMARY KEY (id);


--
-- Name: assessment_tasks assessment_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_tasks
    ADD CONSTRAINT assessment_tasks_pkey PRIMARY KEY (id);


--
-- Name: compare_drafts compare_drafts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compare_drafts
    ADD CONSTRAINT compare_drafts_pkey PRIMARY KEY (id);


--
-- Name: compare_drafts compare_drafts_task_id_buyer_id_material_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compare_drafts
    ADD CONSTRAINT compare_drafts_task_id_buyer_id_material_code_key UNIQUE (task_id, buyer_id, material_code);


--
-- Name: contract_templates contract_templates_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contract_templates
    ADD CONSTRAINT contract_templates_name_key UNIQUE (name);


--
-- Name: contract_templates contract_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contract_templates
    ADD CONSTRAINT contract_templates_pkey PRIMARY KEY (id);


--
-- Name: contracts contracts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT contracts_pkey PRIMARY KEY (id);


--
-- Name: inquiry_requests inquiry_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inquiry_requests
    ADD CONSTRAINT inquiry_requests_pkey PRIMARY KEY (id);


--
-- Name: inquiry_suppliers inquiry_suppliers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inquiry_suppliers
    ADD CONSTRAINT inquiry_suppliers_pkey PRIMARY KEY (id);


--
-- Name: inquiry_task_items inquiry_task_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inquiry_task_items
    ADD CONSTRAINT inquiry_task_items_pkey PRIMARY KEY (id);


--
-- Name: inquiry_tasks inquiry_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inquiry_tasks
    ADD CONSTRAINT inquiry_tasks_pkey PRIMARY KEY (id);


--
-- Name: materials materials_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.materials
    ADD CONSTRAINT materials_pkey PRIMARY KEY (id);


--
-- Name: operation_logs operation_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operation_logs
    ADD CONSTRAINT operation_logs_pkey PRIMARY KEY (id);


--
-- Name: purchase_order_monthly_stats purchase_order_monthly_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_monthly_stats
    ADD CONSTRAINT purchase_order_monthly_stats_pkey PRIMARY KEY (id);


--
-- Name: purchase_order_summary purchase_order_summary_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_summary
    ADD CONSTRAINT purchase_order_summary_pkey PRIMARY KEY (id);


--
-- Name: quotations quotations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quotations
    ADD CONSTRAINT quotations_pkey PRIMARY KEY (id);


--
-- Name: supplier_members supplier_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_members
    ADD CONSTRAINT supplier_members_pkey PRIMARY KEY (id);


--
-- Name: supplier_metrics supplier_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_metrics
    ADD CONSTRAINT supplier_metrics_pkey PRIMARY KEY (id);


--
-- Name: suppliers suppliers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suppliers
    ADD CONSTRAINT suppliers_pkey PRIMARY KEY (id);


--
-- Name: contracts uq_contracts_inquiry_supplier_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT uq_contracts_inquiry_supplier_id UNIQUE (inquiry_supplier_id);


--
-- Name: purchase_order_monthly_stats uq_purchase_order_monthly_supplier_material_month; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_monthly_stats
    ADD CONSTRAINT uq_purchase_order_monthly_supplier_material_month UNIQUE (supplier_code, material_code, stat_month);


--
-- Name: purchase_order_summary uq_purchase_order_summary_supplier_material; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_summary
    ADD CONSTRAINT uq_purchase_order_summary_supplier_material UNIQUE (supplier_code, material_code);


--
-- Name: supplier_members uq_supplier_members_supplier_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_members
    ADD CONSTRAINT uq_supplier_members_supplier_user UNIQUE (supplier_id, user_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: warning_messages warning_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.warning_messages
    ADD CONSTRAINT warning_messages_pkey PRIMARY KEY (id);


--
-- Name: ix_assessment_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_items_id ON public.assessment_items USING btree (id);


--
-- Name: ix_assessment_supplier_scores_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_supplier_scores_id ON public.assessment_supplier_scores USING btree (id);


--
-- Name: ix_assessment_supplier_scores_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_supplier_scores_item_id ON public.assessment_supplier_scores USING btree (item_id);


--
-- Name: ix_assessment_supplier_scores_supplier_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_supplier_scores_supplier_id ON public.assessment_supplier_scores USING btree (supplier_id);


--
-- Name: ix_assessment_supplier_scores_task_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_supplier_scores_task_id ON public.assessment_supplier_scores USING btree (task_id);


--
-- Name: ix_assessment_tasks_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_tasks_id ON public.assessment_tasks USING btree (id);


--
-- Name: ix_contracts_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contracts_id ON public.contracts USING btree (id);


--
-- Name: ix_inquiry_requests_bill_no; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inquiry_requests_bill_no ON public.inquiry_requests USING btree (bill_no);


--
-- Name: ix_inquiry_requests_erp_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inquiry_requests_erp_request_id ON public.inquiry_requests USING btree (erp_request_id);


--
-- Name: ix_inquiry_requests_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inquiry_requests_id ON public.inquiry_requests USING btree (id);


--
-- Name: ix_inquiry_requests_material_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inquiry_requests_material_code ON public.inquiry_requests USING btree (material_code);


--
-- Name: ix_inquiry_suppliers_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inquiry_suppliers_id ON public.inquiry_suppliers USING btree (id);


--
-- Name: ix_inquiry_task_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inquiry_task_items_id ON public.inquiry_task_items USING btree (id);


--
-- Name: ix_inquiry_tasks_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inquiry_tasks_id ON public.inquiry_tasks USING btree (id);


--
-- Name: ix_materials_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_materials_code ON public.materials USING btree (code);


--
-- Name: ix_materials_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_materials_id ON public.materials USING btree (id);


--
-- Name: ix_operation_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_operation_logs_id ON public.operation_logs USING btree (id);


--
-- Name: ix_purchase_order_monthly_stats_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_monthly_stats_id ON public.purchase_order_monthly_stats USING btree (id);


--
-- Name: ix_purchase_order_monthly_stats_material_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_monthly_stats_material_code ON public.purchase_order_monthly_stats USING btree (material_code);


--
-- Name: ix_purchase_order_monthly_stats_stat_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_monthly_stats_stat_month ON public.purchase_order_monthly_stats USING btree (stat_month);


--
-- Name: ix_purchase_order_monthly_stats_supplier_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_monthly_stats_supplier_code ON public.purchase_order_monthly_stats USING btree (supplier_code);


--
-- Name: ix_purchase_order_summary_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_summary_id ON public.purchase_order_summary USING btree (id);


--
-- Name: ix_purchase_order_summary_latest_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_summary_latest_date ON public.purchase_order_summary USING btree (latest_date);


--
-- Name: ix_purchase_order_summary_material_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_summary_material_code ON public.purchase_order_summary USING btree (material_code);


--
-- Name: ix_purchase_order_summary_supplier_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_summary_supplier_code ON public.purchase_order_summary USING btree (supplier_code);


--
-- Name: ix_quotations_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quotations_id ON public.quotations USING btree (id);


--
-- Name: ix_supplier_members_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_supplier_members_id ON public.supplier_members USING btree (id);


--
-- Name: ix_supplier_members_supplier_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_supplier_members_supplier_id ON public.supplier_members USING btree (supplier_id);


--
-- Name: ix_supplier_members_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_supplier_members_user_id ON public.supplier_members USING btree (user_id);


--
-- Name: ix_supplier_metrics_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_supplier_metrics_id ON public.supplier_metrics USING btree (id);


--
-- Name: ix_suppliers_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_suppliers_id ON public.suppliers USING btree (id);


--
-- Name: ix_suppliers_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_suppliers_name ON public.suppliers USING btree (name);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: ix_users_username; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_username ON public.users USING btree (username);


--
-- Name: ix_warning_messages_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_warning_messages_id ON public.warning_messages USING btree (id);


--
-- Name: assessment_supplier_scores assessment_supplier_scores_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_supplier_scores
    ADD CONSTRAINT assessment_supplier_scores_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.assessment_items(id);


--
-- Name: assessment_supplier_scores assessment_supplier_scores_scored_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_supplier_scores
    ADD CONSTRAINT assessment_supplier_scores_scored_by_fkey FOREIGN KEY (scored_by) REFERENCES public.users(id);


--
-- Name: assessment_supplier_scores assessment_supplier_scores_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_supplier_scores
    ADD CONSTRAINT assessment_supplier_scores_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id);


--
-- Name: assessment_supplier_scores assessment_supplier_scores_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_supplier_scores
    ADD CONSTRAINT assessment_supplier_scores_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.assessment_tasks(id);


--
-- Name: assessment_tasks assessment_tasks_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_tasks
    ADD CONSTRAINT assessment_tasks_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: compare_drafts compare_drafts_buyer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compare_drafts
    ADD CONSTRAINT compare_drafts_buyer_id_fkey FOREIGN KEY (buyer_id) REFERENCES public.users(id);


--
-- Name: compare_drafts compare_drafts_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compare_drafts
    ADD CONSTRAINT compare_drafts_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.inquiry_tasks(id);


--
-- Name: contracts contracts_generated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT contracts_generated_by_fkey FOREIGN KEY (generated_by) REFERENCES public.users(id);


--
-- Name: contracts contracts_inquiry_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT contracts_inquiry_supplier_id_fkey FOREIGN KEY (inquiry_supplier_id) REFERENCES public.inquiry_suppliers(id);


--
-- Name: contracts contracts_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT contracts_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.inquiry_tasks(id);


--
-- Name: inquiry_suppliers inquiry_suppliers_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inquiry_suppliers
    ADD CONSTRAINT inquiry_suppliers_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id);


--
-- Name: inquiry_suppliers inquiry_suppliers_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inquiry_suppliers
    ADD CONSTRAINT inquiry_suppliers_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.inquiry_tasks(id);


--
-- Name: inquiry_task_items inquiry_task_items_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inquiry_task_items
    ADD CONSTRAINT inquiry_task_items_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.inquiry_requests(id);


--
-- Name: inquiry_task_items inquiry_task_items_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inquiry_task_items
    ADD CONSTRAINT inquiry_task_items_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.inquiry_tasks(id);


--
-- Name: inquiry_tasks inquiry_tasks_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inquiry_tasks
    ADD CONSTRAINT inquiry_tasks_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: operation_logs operation_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operation_logs
    ADD CONSTRAINT operation_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: quotations quotations_inquiry_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quotations
    ADD CONSTRAINT quotations_inquiry_supplier_id_fkey FOREIGN KEY (inquiry_supplier_id) REFERENCES public.inquiry_suppliers(id);


--
-- Name: quotations quotations_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quotations
    ADD CONSTRAINT quotations_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.inquiry_task_items(id);


--
-- Name: supplier_members supplier_members_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_members
    ADD CONSTRAINT supplier_members_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(id);


--
-- Name: supplier_members supplier_members_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_members
    ADD CONSTRAINT supplier_members_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id);


--
-- Name: supplier_members supplier_members_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_members
    ADD CONSTRAINT supplier_members_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: supplier_metrics supplier_metrics_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_metrics
    ADD CONSTRAINT supplier_metrics_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id);


--
-- Name: supplier_metrics supplier_metrics_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_metrics
    ADD CONSTRAINT supplier_metrics_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.inquiry_tasks(id);


--
-- Name: suppliers suppliers_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suppliers
    ADD CONSTRAINT suppliers_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: warning_messages warning_messages_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.warning_messages
    ADD CONSTRAINT warning_messages_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id);


--
-- PostgreSQL database dump complete
--

\unrestrict YlqtNaUoriPlrZfMAEccDFxeqluaeuELJ39LPKT8z9ApccflVQxsSamtvVPg0vn

