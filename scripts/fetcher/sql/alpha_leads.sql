-- 催收语音是否有效

select user_id
,loan_no
,new_flag
,mobile
,call_time
,concat(mobile,'-',replaceRegexpAll(cast(call_time as String),'-| |:','')) match_key
,talk_duration
,repay_type
,reloan_flag
,loan_status
,collection_status
,dpd
,promise_repay_date
,init_due_date
,cur_due_date
,approved_principal
,approved_amount
,product_code
,product_name
,current_loan_seq
,history_loan_cnt
,total_loan_cnt
,paidoff_loan_cnt
,age
,gender
,date_of_birth
,marital_status
,number_of_children
,education
,home_address
,occupation
,industry
,position
,monthly_income
,expenditure
,company_location
,seats_name
,chat_group
,record_url
from
(
    select a.user_id as user_id
    ,a.call_status as call_status
    ,a.talk_time as talk_duration
    ,a.created_time as call_time
    ,a.record_url as record_url
    ,a.seats_name as seats_name
    ,case 
    when a.group_id=92 then 'H2'
    when a.group_id=93 then 'H1'
    when a.group_id=94 then 'S0'
    end as chat_group
    ,c.loan_no as loan_no
    ,c.mobile as mobile
    ,c.collection_status as collection_status
    ,c.dpd as dpd
    ,c.promise_repay_date as promise_repay_date
    ,d.new_flag as new_flag
    ,d.loan_status as loan_status
    ,d.init_due_date as init_due_date
    ,d.cur_due_date as cur_due_date
    ,d.approved_principal as approved_principal
    ,d.approved_amount as approved_amount
    ,d.product_code as product_code
    ,d.product_name as product_name
    ,e.paid_off_time as paid_off_time
    ,repay_type
    ,reloan_flag
    ,j.current_loan_seq as current_loan_seq
    ,j.history_loan_cnt as history_loan_cnt
    ,k.total_loan_cnt as total_loan_cnt
    ,k.paidoff_loan_cnt as paidoff_loan_cnt
    ,g.age as age
    ,g.gender as gender
    ,g.date_of_birth as date_of_birth
    ,h.marital_status as marital_status
    ,h.number_of_children as number_of_children
    ,h.education as education
    ,h.home_address as home_address
    ,i.occupation as occupation
    ,i.industry as industry
    ,i.position as position
    ,i.monthly_income as monthly_income
    ,i.expenditure as expenditure
    ,i.company_location as company_location
    ,datediff('day',date(a.created_time),d.init_due_date) ddiff
    ,dense_rank() over (partition by c.loan_no order by name_id) rk
    from alpha_collection_ods_tel_name_call a
    left join alpha_collection_ods_tel_name c
    on a.name_id = c.id
    left join alpha_lcs_ods_c_loan d
    on c.loan_no = d.loan_no
    left join  -- 12小时内是否还款或展期
    (
        select loan_no
        ,paid_off_time
        ,case when repay_type = 10 then 'extend' else 'repay' end as repay_type
        from alpha_lcs_ods_c_repay_apply
        where date(paid_off_time) >= '2026-03-01'
        and remark in ('还款申请成功')
    ) e
    on c.loan_no = e.loan_no and timediff(e.paid_off_time, a.created_time) <= 12*3600
    left join  -- 当天是否复借
    (
        select a.loan_no
        ,case when b.loan_no is not null then 1 else 0 end as reloan_flag
        ,a.effective_date
        from 
        (
            select loan_no
            ,cast(user_id as UInt64) as user_id
            ,effective_date
            ,row_number() over (partition by user_id order by effective_date) rn
            from alpha_lcs_ods_c_loan
            where loan_status not in (22,23)
        ) a
        left join
        (
            select loan_no
            ,cast(user_id as UInt64) as user_id
            ,row_number() over (partition by user_id order by effective_date) rn
            from alpha_lcs_ods_c_loan
            where loan_status not in (22,23)
        ) b
        on a.user_id = b.user_id and a.rn + 1 = b.rn
        where effective_date >= '2026-03-01'
    ) f
    on c.loan_no = f.loan_no and date(f.effective_date) = date(a.created_time)
    left join
    (
        select user_id
        ,age
        ,gender
        ,date_of_birth
        from
        (
            select cast(user_id as UInt64) as user_id
            ,age
            ,gender
            ,date_of_birth
            ,row_number() over (partition by user_id order by created_time desc, id desc) as rn
            from alpha_cis_ods_t_user_real_name
            where deleted = 0
        ) t
        where rn = 1
    ) g
    on c.user_id = g.user_id
    left join
    (
        select user_id
        ,marital_status
        ,number_of_children
        ,education
        ,home_address
        from
        (
            select cast(user_id as UInt64) as user_id
            ,marital_status
            ,number_of_children
            ,education
            ,home_address
            ,row_number() over (partition by user_id order by created_time desc, id desc) as rn
            from alpha_cis_ods_t_user_base_info
            where deleted = 0
        ) t
        where rn = 1
    ) h
    on c.user_id = h.user_id
    left join
    (
        select user_id
        ,occupation
        ,industry
        ,position
        ,monthly_income
        ,expenditure
        ,company_location
        from
        (
            select cast(user_id as UInt64) as user_id
            ,occupation
            ,industry
            ,position
            ,monthly_income
            ,expenditure
            ,company_location
            ,row_number() over (partition by user_id order by created_time desc, id desc) as rn
            from alpha_cis_ods_t_user_job
            where deleted = 0
        ) t
        where rn = 1
    ) i
    on c.user_id = i.user_id
    left join
    (
        select loan_no
        ,user_id
        ,rn as current_loan_seq
        ,rn - 1 as history_loan_cnt
        from
        (
            select loan_no
            ,cast(user_id as UInt64) as user_id
            ,row_number() over (partition by user_id order by effective_date, id) as rn
            from alpha_lcs_ods_c_loan
            where loan_status not in (22,23)
        ) t
    ) j
    on c.loan_no = j.loan_no
    left join
    (
        select cast(user_id as UInt64) as user_id
        ,count(*) as total_loan_cnt
        ,sum(if(loan_status = 5,1,0)) as paidoff_loan_cnt
        from alpha_lcs_ods_c_loan
        where loan_status not in (22,23)
        group by 1
    ) k
    on c.user_id = k.user_id
) t
where rk = 1
and talk_duration between 20 and 60
and date(call_time) >= '2026-04-01'