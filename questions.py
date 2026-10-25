"""AA1 care questions (form version Nov 2025) -> fillable field names + chat topics."""
CARE_QUESTIONS = [
 # (q, title, topic prompts for the chat, main free-text field)
 (29,"Getting out of bed / into bed","How do they get out of bed in the morning and into bed at night? Does anyone help? How long does it take?","29-8"),
 (30,"Toilet needs","Getting to/using the toilet, incontinence, pads, how often help is needed each day.","30-9"),
 (31,"Washing, bathing, showering, appearance","Washing, getting in/out of the bath or shower, shaving, hair, any falls or fear in the bathroom.","31-12"),
 (32,"Dressing and undressing","Buttons, zips, socks/shoes, choosing suitable clothes, how long it takes.","32-10"),
 (33,"Moving around indoors","Stairs, walking between rooms, getting up from a chair, walking aids.","33-11"),
 (34,"Falls and stumbles","When they last fell, how often, what happens, can they get up alone.","34-1"),
 (35,"Cutting up food, eating, drinking","Cutting food, holding cups, reminders to eat or drink.","35-7"),
 (36,"Medicines and treatment","Reminders, opening packets, managing doses, mistakes made.","36-8"),
 (37,"Communicating","Hearing, sight, speech, understanding others, using the phone.","37-14"),
 (39,"Hobbies, social and religious activities","Things they do or would like to do and the help needed.","39-1"),
 (40,"Someone keeping an eye on them (day)","Confusion, wandering, safety risks, how long they can safely be left.","40-12"),
 (42,"Help during the night","Settling, turning over, toilet at night, how many times and for how long.","42-18"),
 (44,"Someone watching over them (night)","Does someone need to be awake to watch over them at night, and why.","313"),
]
EXTRA_FIELDS = {"days_week_day":"38","days_keep_eye":"41","nights_week":"43","nights_watch":"314",
 "safe_alone":"40-10","fall_detail":"34-4","last_fell":"34-5","falls_month":"34-7","falls_year":"34-8",
 "anything_else_care":"315","extra_info":"354","care_start":"28"}
PERSONAL_FIELDS = {"surname":"01-01i","other_names":"01-01ii","title":"01-01iii","dob":"01-03Date",
 "addr1":"01-05line1","addr2":"01-05line2","addr3":"01-05line3","postcode":"01-05line4","phone":"01-06i",
 "gp_name":"19","gp_addr1":"19_1","gp_postcode":"19-4","gp_phone":"19-5"}
CONDITION_FIELDS = [("16_1","16_2","16_3","16_4"),("16_5","16_6","16_7","16_8"),("16_9","16_10","16_11","16_12"),
 ("16_13","16_14","16_15","16_16"),("16_17","16_18","16_19","16_20"),("16_21","16_22","16_23","16_24")]
# Never auto-filled: NI number, bank details (Q335-341), signatures/dates, tick boxes (user ticks yes/no by hand; we list which).
