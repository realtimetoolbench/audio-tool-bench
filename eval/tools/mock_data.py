"""
Unified Mock Data for Audio Tool Bench

All mock data is centralized here for consistency between:
1. Tool execution eval/tools/*.py
2. Test case generation scripts/generate_from_seeds.py
"""

# ============ Travel Booking ============

FLIGHTS = {
    ("Beijing", "Shanghai"): [
        {"flight_id": "flt_bj_sh_001", "flight_no": "CA1234", "airline": "Air China", "departure": "08:00", "arrival": "10:30", "price": 800, "class": "economy", "available": True},
        {"flight_id": "flt_bj_sh_002", "flight_no": "MU5678", "airline": "China Eastern", "departure": "10:00", "arrival": "12:30", "price": 750, "class": "economy", "available": True},
        {"flight_id": "flt_bj_sh_003", "flight_no": "CA1456", "airline": "Air China", "departure": "14:00", "arrival": "16:30", "price": 850, "class": "economy", "available": True},
        {"flight_id": "flt_bj_sh_004", "flight_no": "MU5890", "airline": "China Eastern", "departure": "18:00", "arrival": "20:30", "price": 900, "class": "economy", "available": True},
    ],
    ("Shanghai", "Beijing"): [
        {"flight_id": "flt_sh_bj_001", "flight_no": "CA1235", "airline": "Air China", "departure": "07:00", "arrival": "09:30", "price": 780, "class": "economy", "available": True},
        {"flight_id": "flt_sh_bj_002", "flight_no": "MU5679", "airline": "China Eastern", "departure": "12:00", "arrival": "14:30", "price": 720, "class": "economy", "available": True},
    ],
    ("Beijing", "Guangzhou"): [
        {"flight_id": "flt_bj_gz_001", "flight_no": "CZ3456", "airline": "China Southern", "departure": "09:00", "arrival": "12:00", "price": 1200, "class": "economy", "available": True},
        {"flight_id": "flt_bj_gz_002", "flight_no": "CA1789", "airline": "Air China", "departure": "15:00", "arrival": "18:00", "price": 1150, "class": "economy", "available": True},
    ],
    ("Guangzhou", "Beijing"): [
        {"flight_id": "flt_gz_bj_001", "flight_no": "CZ3457", "airline": "China Southern", "departure": "08:00", "arrival": "11:00", "price": 1180, "class": "economy", "available": True},
        {"flight_id": "flt_gz_bj_002", "flight_no": "MU5102", "airline": "China Eastern", "departure": "10:30", "arrival": "13:30", "price": 1050, "class": "economy", "available": True},
        {"flight_id": "flt_gz_bj_003", "flight_no": "CA1790", "airline": "Air China", "departure": "14:00", "arrival": "17:00", "price": 1100, "class": "economy", "available": True},
    ],
    ("Beijing", "Chengdu"): [
        {"flight_id": "flt_bj_cd_001", "flight_no": "CA4102", "airline": "Air China", "departure": "07:30", "arrival": "10:30", "price": 1050, "class": "economy", "available": True},
        {"flight_id": "flt_bj_cd_002", "flight_no": "3U8888", "airline": "Sichuan Airlines", "departure": "13:00", "arrival": "16:00", "price": 980, "class": "economy", "available": True},
    ],
    ("Chengdu", "Beijing"): [
        {"flight_id": "flt_cd_bj_001", "flight_no": "CA4103", "airline": "Air China", "departure": "11:00", "arrival": "14:00", "price": 1020, "class": "economy", "available": True},
    ],
    ("Beijing", "Shenzhen"): [
        {"flight_id": "flt_bj_sz_001", "flight_no": "CZ3100", "airline": "China Southern", "departure": "08:30", "arrival": "11:45", "price": 1350, "class": "economy", "available": True},
        {"flight_id": "flt_bj_sz_002", "flight_no": "CA1301", "airline": "Air China", "departure": "14:20", "arrival": "17:30", "price": 1280, "class": "economy", "available": True},
    ],
    ("Shenzhen", "Beijing"): [
        {"flight_id": "flt_sz_bj_001", "flight_no": "CZ3101", "airline": "China Southern", "departure": "09:00", "arrival": "12:10", "price": 1320, "class": "economy", "available": True},
    ],
    ("Shanghai", "Shenzhen"): [
        {"flight_id": "flt_sh_sz_001", "flight_no": "MU5318", "airline": "China Eastern", "departure": "07:45", "arrival": "10:00", "price": 980, "class": "economy", "available": True},
        {"flight_id": "flt_sh_sz_002", "flight_no": "CZ3564", "airline": "China Southern", "departure": "13:30", "arrival": "15:50", "price": 920, "class": "economy", "available": True},
    ],
    ("Shenzhen", "Shanghai"): [
        {"flight_id": "flt_sz_sh_001", "flight_no": "MU5319", "airline": "China Eastern", "departure": "11:00", "arrival": "13:20", "price": 950, "class": "economy", "available": True},
    ],
    ("Shanghai", "Chengdu"): [
        {"flight_id": "flt_sh_cd_001", "flight_no": "MU5401", "airline": "China Eastern", "departure": "09:00", "arrival": "12:00", "price": 1080, "class": "economy", "available": True},
        {"flight_id": "flt_sh_cd_002", "flight_no": "3U8898", "airline": "Sichuan Airlines", "departure": "15:30", "arrival": "18:30", "price": 1020, "class": "economy", "available": True},
    ],
    ("Chengdu", "Shanghai"): [
        {"flight_id": "flt_cd_sh_001", "flight_no": "MU5402", "airline": "China Eastern", "departure": "13:00", "arrival": "16:00", "price": 1050, "class": "economy", "available": True},
    ],
    ("Shanghai", "Guangzhou"): [
        {"flight_id": "flt_sh_gz_001", "flight_no": "CZ3530", "airline": "China Southern", "departure": "10:00", "arrival": "12:30", "price": 1100, "class": "economy", "available": True},
        {"flight_id": "flt_sh_gz_002", "flight_no": "MU5305", "airline": "China Eastern", "departure": "16:00", "arrival": "18:30", "price": 1050, "class": "economy", "available": True},
    ],
    ("Guangzhou", "Shanghai"): [
        {"flight_id": "flt_gz_sh_001", "flight_no": "CZ3531", "airline": "China Southern", "departure": "13:30", "arrival": "16:00", "price": 1080, "class": "economy", "available": True},
    ],
    ("Beijing", "Wuhan"): [
        {"flight_id": "flt_bj_wh_001", "flight_no": "CA1403", "airline": "Air China", "departure": "10:30", "arrival": "12:40", "price": 880, "class": "economy", "available": True},
    ],
    ("Wuhan", "Beijing"): [
        {"flight_id": "flt_wh_bj_001", "flight_no": "CA1404", "airline": "Air China", "departure": "14:00", "arrival": "16:10", "price": 850, "class": "economy", "available": True},
    ],
}

TRAINS = {
    ("Beijing", "Shanghai"): [
        {"train_id": "trn_bj_sh_001", "train_no": "G1", "type": "High-speed", "departure": "06:00", "arrival": "10:28", "duration": "4h28m", "price_second": 553, "price_first": 933, "seats_available": True},
        {"train_id": "trn_bj_sh_002", "train_no": "G3", "type": "High-speed", "departure": "07:00", "arrival": "11:35", "duration": "4h35m", "price_second": 553, "price_first": 933, "seats_available": True},
        {"train_id": "trn_bj_sh_003", "train_no": "D321", "type": "Express", "departure": "08:30", "arrival": "16:45", "duration": "8h15m", "price_second": 309, "price_first": 494, "seats_available": True},
    ],
    ("Shanghai", "Beijing"): [
        {"train_id": "trn_sh_bj_001", "train_no": "G2", "type": "High-speed", "departure": "07:00", "arrival": "11:33", "duration": "4h33m", "price_second": 553, "price_first": 933, "seats_available": True},
        {"train_id": "trn_sh_bj_002", "train_no": "G4", "type": "High-speed", "departure": "09:00", "arrival": "13:28", "duration": "4h28m", "price_second": 553, "price_first": 933, "seats_available": True},
    ],
    ("Beijing", "Chengdu"): [
        {"train_id": "trn_bj_cd_001", "train_no": "G89", "type": "High-speed", "departure": "08:05", "arrival": "19:29", "duration": "11h24m", "price_second": 778, "price_first": 1246, "seats_available": True},
        {"train_id": "trn_bj_cd_002", "train_no": "K117", "type": "Express", "departure": "19:40", "arrival": "next day 17:08", "duration": "21h28m", "price_second": 263, "price_first": 419, "seats_available": True},
    ],
    ("Chengdu", "Beijing"): [
        {"train_id": "trn_cd_bj_001", "train_no": "G90", "type": "High-speed", "departure": "08:20", "arrival": "19:42", "duration": "11h22m", "price_second": 778, "price_first": 1246, "seats_available": True},
    ],
    ("Chengdu", "Chongqing"): [
        {"train_id": "trn_cd_cq_001", "train_no": "G8501", "type": "High-speed", "departure": "08:00", "arrival": "09:20", "duration": "1h20m", "price_second": 154, "price_first": 246, "seats_available": True},
        {"train_id": "trn_cd_cq_002", "train_no": "G8503", "type": "High-speed", "departure": "10:00", "arrival": "11:20", "duration": "1h20m", "price_second": 154, "price_first": 246, "seats_available": True},
    ],
    ("Beijing", "Xi'an"): [
        {"train_id": "trn_bj_xa_001", "train_no": "G87", "type": "High-speed", "departure": "07:00", "arrival": "11:58", "duration": "4h58m", "price_second": 515, "price_first": 825, "seats_available": True},
        {"train_id": "trn_bj_xa_002", "train_no": "G25", "type": "High-speed", "departure": "09:00", "arrival": "13:52", "duration": "4h52m", "price_second": 515, "price_first": 825, "seats_available": True},
    ],
    ("Xi'an", "Beijing"): [
        {"train_id": "trn_xa_bj_001", "train_no": "G88", "type": "High-speed", "departure": "08:00", "arrival": "12:50", "duration": "4h50m", "price_second": 515, "price_first": 825, "seats_available": True},
    ],
    ("Beijing", "Nanjing"): [
        {"train_id": "trn_bj_nj_001", "train_no": "G15", "type": "High-speed", "departure": "08:00", "arrival": "11:55", "duration": "3h55m", "price_second": 443, "price_first": 709, "seats_available": True},
        {"train_id": "trn_bj_nj_002", "train_no": "G41", "type": "High-speed", "departure": "12:30", "arrival": "16:28", "duration": "3h58m", "price_second": 443, "price_first": 709, "seats_available": True},
    ],
    ("Nanjing", "Beijing"): [
        {"train_id": "trn_nj_bj_001", "train_no": "G16", "type": "High-speed", "departure": "09:15", "arrival": "13:10", "duration": "3h55m", "price_second": 443, "price_first": 709, "seats_available": True},
    ],
    ("Shanghai", "Hangzhou"): [
        {"train_id": "trn_sh_hz_001", "train_no": "G7509", "type": "High-speed", "departure": "08:30", "arrival": "09:15", "duration": "45m", "price_second": 73, "price_first": 117, "seats_available": True},
        {"train_id": "trn_sh_hz_002", "train_no": "G7531", "type": "High-speed", "departure": "14:00", "arrival": "14:48", "duration": "48m", "price_second": 73, "price_first": 117, "seats_available": True},
    ],
    ("Hangzhou", "Shanghai"): [
        {"train_id": "trn_hz_sh_001", "train_no": "G7510", "type": "High-speed", "departure": "10:00", "arrival": "10:48", "duration": "48m", "price_second": 73, "price_first": 117, "seats_available": True},
    ],
    ("Shanghai", "Suzhou"): [
        {"train_id": "trn_sh_su_001", "train_no": "G7001", "type": "High-speed", "departure": "09:00", "arrival": "09:30", "duration": "30m", "price_second": 40, "price_first": 65, "seats_available": True},
        {"train_id": "trn_sh_su_002", "train_no": "G7025", "type": "High-speed", "departure": "15:00", "arrival": "15:28", "duration": "28m", "price_second": 40, "price_first": 65, "seats_available": True},
    ],
    ("Suzhou", "Shanghai"): [
        {"train_id": "trn_su_sh_001", "train_no": "G7002", "type": "High-speed", "departure": "10:15", "arrival": "10:45", "duration": "30m", "price_second": 40, "price_first": 65, "seats_available": True},
    ],
    ("Chengdu", "Xi'an"): [
        {"train_id": "trn_cd_xa_001", "train_no": "G306", "type": "High-speed", "departure": "07:50", "arrival": "11:33", "duration": "3h43m", "price_second": 405, "price_first": 648, "seats_available": True},
    ],
    ("Xi'an", "Chengdu"): [
        {"train_id": "trn_xa_cd_001", "train_no": "G305", "type": "High-speed", "departure": "12:00", "arrival": "15:45", "duration": "3h45m", "price_second": 405, "price_first": 648, "seats_available": True},
    ],
    ("Nanjing", "Shanghai"): [
        {"train_id": "trn_nj_sh_001", "train_no": "G7001N", "type": "High-speed", "departure": "08:00", "arrival": "09:20", "duration": "1h20m", "price_second": 140, "price_first": 224, "seats_available": True},
    ],
    ("Shanghai", "Nanjing"): [
        {"train_id": "trn_sh_nj_001", "train_no": "G7002N", "type": "High-speed", "departure": "10:30", "arrival": "11:55", "duration": "1h25m", "price_second": 140, "price_first": 224, "seats_available": True},
    ],
}

HOTELS = {
    "Shanghai": [
        {"hotel_id": "hotel_sh_001", "name": "Waldorf Astoria Shanghai on the Bund", "location": "the Bund", "stars": 5, "price": 1200, "rating": 4.8},
        {"hotel_id": "hotel_sh_002", "name": "Pudong Shangri-La", "location": "Pudong", "stars": 5, "price": 1000, "rating": 4.7},
        {"hotel_id": "hotel_sh_003", "name": "Hyatt on the Bund", "location": "the Bund", "stars": 4, "price": 750, "rating": 4.5},
        {"hotel_id": "hotel_sh_004", "name": "Home Inn the Bund", "location": "the Bund", "stars": 3, "price": 400, "rating": 4.2},
        {"hotel_id": "hotel_sh_005", "name": "Hanting Hotel People's Square", "location": "People's Square", "stars": 3, "price": 350, "rating": 4.0},
    ],
    "Hangzhou": [
        {"hotel_id": "hotel_hz_001", "name": "West Lake State Guesthouse", "location": "West Lake", "stars": 5, "price": 1500, "rating": 4.9},
        {"hotel_id": "hotel_hz_002", "name": "Hilton Hangzhou West Lake", "location": "West Lake", "stars": 4, "price": 800, "rating": 4.6},
        {"hotel_id": "hotel_hz_003", "name": "Home Inn West Lake", "location": "West Lake", "stars": 3, "price": 450, "rating": 4.3},
    ],
    "Beijing": [
        {"hotel_id": "hotel_bj_001", "name": "The Peninsula Beijing", "location": "Wangfujing", "stars": 5, "price": 1800, "rating": 4.9},
        {"hotel_id": "hotel_bj_002", "name": "Park Hyatt Beijing", "location": "CBD", "stars": 5, "price": 1500, "rating": 4.8},
        {"hotel_id": "hotel_bj_003", "name": "Holiday Inn Express", "location": "Zhongguancun", "stars": 3, "price": 450, "rating": 4.2},
        {"hotel_id": "hotel_bj_004", "name": "Beijing Hotel", "location": "Downtown", "stars": 4, "price": 600, "rating": 4.4},
        {"hotel_id": "hotel_bj_005", "name": "Novotel Beijing Peace", "location": "Downtown", "stars": 4, "price": 550, "rating": 4.5},
        {"hotel_id": "hotel_bj_006", "name": "Grand Mercure Beijing", "location": "Downtown", "stars": 4, "price": 700, "rating": 4.6},
        {"hotel_id": "hotel_bj_007", "name": "Home Inn Dongzhimen", "location": "Downtown", "stars": 3, "price": 350, "rating": 4.1},
    ],
    "Guangzhou": [
        {"hotel_id": "hotel_gz_001", "name": "The Ritz-Carlton Guangzhou", "location": "Zhujiang New Town", "stars": 5, "price": 1600, "rating": 4.8},
        {"hotel_id": "hotel_gz_002", "name": "Four Seasons Guangzhou", "location": "Zhujiang New Town", "stars": 5, "price": 1700, "rating": 4.9},
        {"hotel_id": "hotel_gz_003", "name": "White Swan Hotel", "location": "Shamian Island", "stars": 5, "price": 1100, "rating": 4.7},
        {"hotel_id": "hotel_gz_004", "name": "Hanting Hotel Tianhe", "location": "Tianhe", "stars": 3, "price": 380, "rating": 4.2},
    ],
    "Shenzhen": [
        {"hotel_id": "hotel_sz_001", "name": "The St. Regis Shenzhen", "location": "Futian", "stars": 5, "price": 1800, "rating": 4.9},
        {"hotel_id": "hotel_sz_002", "name": "Grand Hyatt Shenzhen", "location": "Luohu", "stars": 5, "price": 1300, "rating": 4.7},
        {"hotel_id": "hotel_sz_003", "name": "Holiday Inn Nanshan", "location": "Nanshan", "stars": 4, "price": 620, "rating": 4.5},
        {"hotel_id": "hotel_sz_004", "name": "Home Inn Futian CBD", "location": "Futian", "stars": 3, "price": 400, "rating": 4.1},
    ],
    "Wuhan": [
        {"hotel_id": "hotel_wh_001", "name": "Shangri-La Wuhan", "location": "Hankou", "stars": 5, "price": 900, "rating": 4.7},
        {"hotel_id": "hotel_wh_002", "name": "Wanda Realm Wuhan", "location": "Wuchang", "stars": 4, "price": 550, "rating": 4.4},
        {"hotel_id": "hotel_wh_003", "name": "Home Inn Guanggu", "location": "Guanggu", "stars": 3, "price": 320, "rating": 4.0},
    ],
    "Nanjing": [
        {"hotel_id": "hotel_nj_001", "name": "InterContinental Nanjing", "location": "Xinjiekou", "stars": 5, "price": 1200, "rating": 4.8},
        {"hotel_id": "hotel_nj_002", "name": "Sofitel Nanjing Galaxy", "location": "Gulou", "stars": 5, "price": 1000, "rating": 4.7},
        {"hotel_id": "hotel_nj_003", "name": "Jinling Hotel Nanjing", "location": "Xinjiekou", "stars": 4, "price": 650, "rating": 4.5},
        {"hotel_id": "hotel_nj_004", "name": "Hanting Hotel Xuanwu", "location": "Xuanwu", "stars": 3, "price": 350, "rating": 4.1},
    ],
    "Chongqing": [
        {"hotel_id": "hotel_cq_001", "name": "JW Marriott Chongqing", "location": "Yuzhong", "stars": 5, "price": 1100, "rating": 4.8},
        {"hotel_id": "hotel_cq_002", "name": "Hilton Chongqing", "location": "Yuzhong", "stars": 5, "price": 950, "rating": 4.7},
        {"hotel_id": "hotel_cq_003", "name": "Holiday Inn Jiangbei", "location": "Jiangbei", "stars": 4, "price": 520, "rating": 4.4},
    ],
    "Suzhou": [
        {"hotel_id": "hotel_su_001", "name": "Shangri-La Suzhou", "location": "Suzhou Industrial Park", "stars": 5, "price": 1050, "rating": 4.8},
        {"hotel_id": "hotel_su_002", "name": "Pan Pacific Suzhou", "location": "Gusu", "stars": 5, "price": 900, "rating": 4.7},
        {"hotel_id": "hotel_su_003", "name": "Home Inn Pingjiang", "location": "Pingjiang", "stars": 3, "price": 330, "rating": 4.2},
    ],
}

RENTAL_CARS = {
    "Beijing": [
        {"car_id": "car_bj_001", "model": "Volkswagen Lavida", "type": "economy", "seats": 5, "price_per_day": 150, "insurance": 30, "rating": 4.5},
        {"car_id": "car_bj_002", "model": "Honda Accord", "type": "comfort", "seats": 5, "price_per_day": 250, "insurance": 50, "rating": 4.7},
        {"car_id": "car_bj_003", "model": "Audi A6", "type": "luxury", "seats": 5, "price_per_day": 500, "insurance": 80, "rating": 4.8},
        {"car_id": "car_bj_004", "model": "Buick GL8", "type": "business", "seats": 7, "price_per_day": 400, "insurance": 60, "rating": 4.6},
    ],
    "Shanghai": [
        {"car_id": "car_sh_001", "model": "Toyota Corolla", "type": "economy", "seats": 5, "price_per_day": 160, "insurance": 30, "rating": 4.4},
        {"car_id": "car_sh_002", "model": "Volkswagen Passat", "type": "comfort", "seats": 5, "price_per_day": 280, "insurance": 50, "rating": 4.6},
        {"car_id": "car_sh_003", "model": "BMW 5 Series", "type": "luxury", "seats": 5, "price_per_day": 600, "insurance": 100, "rating": 4.9},
    ],
    "Chengdu": [
        {"car_id": "car_cd_001", "model": "Nissan Sylphy", "type": "economy", "seats": 5, "price_per_day": 140, "insurance": 25, "rating": 4.3},
        {"car_id": "car_cd_002", "model": "Toyota Camry", "type": "comfort", "seats": 5, "price_per_day": 260, "insurance": 45, "rating": 4.7},
    ],
}

RESTAURANTS = {
    "Beijing": [
        {"restaurant_id": "rst_bj_001", "name": "Shu Xiang Yuan", "cuisine": "Sichuan", "location": "Downtown", "rating": 4.5},
        {"restaurant_id": "rst_bj_002", "name": "Mala Youhuo", "cuisine": "Sichuan", "location": "Chaoyang", "rating": 4.3},
        {"restaurant_id": "rst_bj_003", "name": "Jingwei Zhai", "cuisine": "Beijing", "location": "Downtown", "rating": 4.7},
        {"restaurant_id": "rst_bj_004", "name": "Quanjude Roast Duck", "cuisine": "Beijing", "location": "Qianmen", "rating": 4.6},
        {"restaurant_id": "rst_bj_005", "name": "Chuan Ban", "cuisine": "Sichuan", "location": "CBD", "rating": 4.4},
        {"restaurant_id": "rst_bj_006", "name": "Da Dong Roast Duck", "cuisine": "Beijing", "location": "CBD", "rating": 4.8},
        {"restaurant_id": "rst_bj_007", "name": "Beijing Garden", "cuisine": "Chinese", "location": "CBD", "rating": 4.7},
        {"restaurant_id": "rst_bj_008", "name": "Imperial Kitchen", "cuisine": "Chinese", "location": "CBD", "rating": 4.6},
        {"restaurant_id": "rst_bj_009", "name": "China Palace", "cuisine": "Chinese", "location": "CBD", "rating": 4.5},
        {"restaurant_id": "rst_bj_010", "name": "Golden Dragon", "cuisine": "Chinese", "location": "CBD", "rating": 4.3},
        {"restaurant_id": "rst_bj_011", "name": "Green Lotus", "cuisine": "Vegetarian", "location": "Wangfujing", "rating": 4.6},
    ],
    "Shanghai": [
        {"restaurant_id": "rst_sh_001", "name": "Chuanfu Laozao", "cuisine": "Sichuan", "location": "Downtown", "rating": 4.6},
        {"restaurant_id": "rst_sh_002", "name": "Shanghai Classic", "cuisine": "Shanghainese", "location": "Pudong", "rating": 4.4},
        {"restaurant_id": "rst_sh_003", "name": "Xiao Nan Guo", "cuisine": "Shanghainese", "location": "Pudong", "rating": 4.5},
    ],
    "Chengdu": [
        {"restaurant_id": "rst_cd_001", "name": "Chen Mapo Tofu", "cuisine": "Sichuan", "location": "Downtown", "rating": 4.7},
        {"restaurant_id": "rst_cd_002", "name": "Lao Ma Tou Hotpot", "cuisine": "Hotpot", "location": "Jinjiang", "rating": 4.8},
    ],
    "Guangzhou": [
        {"restaurant_id": "rst_gz_001", "name": "Bingsheng Restaurant", "cuisine": "Cantonese", "location": "Tianhe", "rating": 4.7},
        {"restaurant_id": "rst_gz_002", "name": "Tao Heung", "cuisine": "Cantonese", "location": "Yuexiu", "rating": 4.5},
        {"restaurant_id": "rst_gz_003", "name": "Panxi Restaurant", "cuisine": "Cantonese", "location": "Liwan", "rating": 4.6},
    ],
    "Shenzhen": [
        {"restaurant_id": "rst_sz_001", "name": "Lao Sichuan", "cuisine": "Sichuan", "location": "Futian", "rating": 4.5},
        {"restaurant_id": "rst_sz_002", "name": "Din Tai Fung Shenzhen", "cuisine": "Taiwanese", "location": "Nanshan", "rating": 4.6},
        {"restaurant_id": "rst_sz_003", "name": "Jiang Hotpot Shenzhen", "cuisine": "Hotpot", "location": "Luohu", "rating": 4.4},
    ],
    "Wuhan": [
        {"restaurant_id": "rst_wh_001", "name": "Cai Lin Ji Hot Noodles", "cuisine": "Hubei", "location": "Hankou", "rating": 4.6},
        {"restaurant_id": "rst_wh_002", "name": "Yangtze River Restaurant", "cuisine": "Hubei", "location": "Wuchang", "rating": 4.4},
    ],
    "Nanjing": [
        {"restaurant_id": "rst_nj_001", "name": "Nanjing Impressions", "cuisine": "Jiangsu", "location": "Xinjiekou", "rating": 4.7},
        {"restaurant_id": "rst_nj_002", "name": "Lao Men Dong Restaurant", "cuisine": "Jiangsu", "location": "Qinhuai", "rating": 4.5},
    ],
    "Chongqing": [
        {"restaurant_id": "rst_cq_001", "name": "Liuyishou Hotpot", "cuisine": "Hotpot", "location": "Yuzhong", "rating": 4.8},
        {"restaurant_id": "rst_cq_002", "name": "Xiao Tian E Hotpot", "cuisine": "Hotpot", "location": "Jiangbei", "rating": 4.7},
    ],
    "Suzhou": [
        {"restaurant_id": "rst_su_001", "name": "Songhelou Restaurant", "cuisine": "Jiangsu", "location": "Gusu", "rating": 4.7},
        {"restaurant_id": "rst_su_002", "name": "Dexing Noodle House", "cuisine": "Jiangsu", "location": "Pingjiang", "rating": 4.5},
    ],
}

ATTRACTIONS = {
    "Beijing": [
        {"attraction_id": "attr_bj_001", "name": "Forbidden City", "type": "Historical", "rating": 4.8, "price": 60, "opening_hours": "08:30-17:00", "location": "Dongcheng"},
        {"attraction_id": "attr_bj_002", "name": "Great Wall Badaling", "type": "Historical", "rating": 4.7, "price": 40, "opening_hours": "06:30-19:00", "location": "Yanqing"},
        {"attraction_id": "attr_bj_003", "name": "Summer Palace", "type": "Garden", "rating": 4.6, "price": 30, "opening_hours": "06:30-18:00", "location": "Haidian"},
        {"attraction_id": "attr_bj_004", "name": "Temple of Heaven", "type": "Historical", "rating": 4.5, "price": 15, "opening_hours": "06:00-22:00", "location": "Dongcheng"},
    ],
    "Shanghai": [
        {"attraction_id": "attr_sh_001", "name": "Oriental Pearl Tower", "type": "Modern", "rating": 4.5, "price": 180, "opening_hours": "08:00-22:00", "location": "Pudong"},
        {"attraction_id": "attr_sh_002", "name": "Shanghai Disneyland", "type": "Theme Park", "rating": 4.7, "price": 399, "opening_hours": "09:00-21:00", "location": "Pudong"},
        {"attraction_id": "attr_sh_003", "name": "The Bund", "type": "Sightseeing", "rating": 4.6, "price": 0, "opening_hours": "24 hours", "location": "Huangpu"},
        {"attraction_id": "attr_sh_004", "name": "Yu Garden", "type": "Garden", "rating": 4.4, "price": 40, "opening_hours": "08:30-17:00", "location": "Huangpu"},
    ],
    "Chengdu": [
        {"attraction_id": "attr_cd_001", "name": "Giant Panda Base", "type": "Zoo", "rating": 4.8, "price": 58, "opening_hours": "07:30-18:00", "location": "Chenghua"},
        {"attraction_id": "attr_cd_002", "name": "Wuhou Shrine", "type": "Historical", "rating": 4.5, "price": 50, "opening_hours": "08:00-18:00", "location": "Wuhou"},
        {"attraction_id": "attr_cd_003", "name": "Du Fu Thatched Cottage", "type": "Historical", "rating": 4.4, "price": 50, "opening_hours": "08:00-18:00", "location": "Qingyang"},
        {"attraction_id": "attr_cd_004", "name": "Kuanzhai Alley", "type": "Sightseeing", "rating": 4.3, "price": 0, "opening_hours": "24 hours", "location": "Qingyang"},
    ],
    "Xi'an": [
        {"attraction_id": "attr_xa_001", "name": "Terracotta Warriors", "type": "Historical", "rating": 4.8, "price": 120, "opening_hours": "08:30-17:00", "location": "Lintong"},
        {"attraction_id": "attr_xa_002", "name": "Giant Wild Goose Pagoda", "type": "Historical", "rating": 4.5, "price": 50, "opening_hours": "08:00-18:00", "location": "Yanta"},
        {"attraction_id": "attr_xa_003", "name": "Huaqing Palace", "type": "Historical", "rating": 4.4, "price": 120, "opening_hours": "07:30-19:00", "location": "Lintong"},
        {"attraction_id": "attr_xa_004", "name": "Bell Tower", "type": "Historical", "rating": 4.3, "price": 35, "opening_hours": "08:00-22:00", "location": "Beilin"},
    ],
}

# ============ Life Services ============

DELIVERY_RESTAURANTS = {
    "Beijing": [
        {"delivery_id": "dlv_bj_001", "name": "McDonald's CBD", "cuisine": "Fast Food", "rating": 4.5, "delivery_time": 30, "min_order": 0, "delivery_fee": 5,
         "menu": ["Big Mac Meal and Fries", "Chicken McNuggets and Cola", "Quarter Pounder and Apple Pie"]},
        {"delivery_id": "dlv_bj_002", "name": "Haidilao Hotpot", "cuisine": "Hotpot", "rating": 4.8, "delivery_time": 45, "min_order": 50, "delivery_fee": 8,
         "menu": ["Hotpot Base and Sliced Beef", "Hotpot with Lamb and Vegetables", "Spicy Hotpot Combo"]},
        {"delivery_id": "dlv_bj_003", "name": "Hunan Restaurant", "cuisine": "Hunan", "rating": 4.3, "delivery_time": 25, "min_order": 20, "delivery_fee": 3,
         "menu": ["Spicy Stir-fried Pork and Rice", "Steamed Fish Head with Chili", "Dong'an Chicken and Rice"]},
        {"delivery_id": "dlv_bj_004", "name": "Starbucks CBD", "cuisine": "Coffee", "rating": 4.6, "delivery_time": 20, "min_order": 0, "delivery_fee": 6,
         "menu": ["Caffe Latte and Croissant", "Americano and Sandwich", "Matcha Latte and Muffin"]},
    ],
    "Shanghai": [
        {"delivery_id": "dlv_sh_001", "name": "KFC Lujiazui", "cuisine": "Fast Food", "rating": 4.4, "delivery_time": 25, "min_order": 0, "delivery_fee": 5,
         "menu": ["Original Recipe Chicken and Fries", "Zinger Burger and Coleslaw", "Popcorn Chicken and Corn"]},
        {"delivery_id": "dlv_sh_002", "name": "Yang's Dumplings", "cuisine": "Dumplings", "rating": 4.7, "delivery_time": 30, "min_order": 15, "delivery_fee": 4,
         "menu": ["Pan-fried Pork Dumplings and Wonton Soup", "Steamed Crab Roe Dumplings", "Shrimp Dumplings and Noodle Soup"]},
        {"delivery_id": "dlv_sh_003", "name": "Hey Tea Nanjing Road", "cuisine": "Bubble Tea", "rating": 4.5, "delivery_time": 20, "min_order": 0, "delivery_fee": 5,
         "menu": ["Cheese Tea and Mochi", "Brown Sugar Boba Milk", "Fruit Tea and Egg Waffle"]},
    ],
    "Chengdu": [
        {"delivery_id": "dlv_cd_001", "name": "Shu Da Xia Hotpot", "cuisine": "Hotpot", "rating": 4.8, "delivery_time": 40, "min_order": 60, "delivery_fee": 10,
         "menu": ["Mala Hotpot with Tripe and Duck Blood", "Tomato Hotpot with Beef and Tofu", "Sichuan Pepper Hotpot Combo"]},
        {"delivery_id": "dlv_cd_002", "name": "Bo Bo Chicken", "cuisine": "Sichuan Snacks", "rating": 4.6, "delivery_time": 25, "min_order": 20, "delivery_fee": 4,
         "menu": ["Spicy Bo Bo Chicken Skewers", "Mapo Tofu and Rice", "Dan Dan Noodles and Cold Chicken"]},
        {"delivery_id": "dlv_cd_003", "name": "Luckin Coffee", "cuisine": "Coffee", "rating": 4.4, "delivery_time": 15, "min_order": 0, "delivery_fee": 3,
         "menu": ["Coconut Latte and Toast", "Iced Americano and Cheese Bagel", "Velvet Latte and Cookie"]},
    ],
}

HOME_SERVICES = {
    "Beijing": [
        {"service_id": "svc_bj_001", "name": "Ayi Laile Chaoyang", "service_type": "cleaning", "rating": 4.8, "price_per_hour": 50, "available_time": ["morning", "afternoon", "evening"], "experience_years": 5, "phone": "010-12345678"},
        {"service_id": "svc_bj_002", "name": "Guanjia Bang Haidian", "service_type": "cleaning", "rating": 4.6, "price_per_hour": 55, "available_time": ["morning", "afternoon"], "experience_years": 3, "phone": "010-23456789"},
        {"service_id": "svc_bj_003", "name": "Swan Home Fengtai", "service_type": "nanny", "rating": 4.9, "price_per_day": 300, "available_time": ["all day"], "experience_years": 8, "phone": "010-34567890"},
    ],
    "Shanghai": [
        {"service_id": "svc_sh_001", "name": "58 Home Pudong", "service_type": "cleaning", "rating": 4.7, "price_per_hour": 60, "available_time": ["morning", "afternoon", "evening"], "experience_years": 4, "phone": "021-12345678"},
        {"service_id": "svc_sh_002", "name": "Haokang Home Xuhui", "service_type": "cleaning", "rating": 4.5, "price_per_hour": 50, "available_time": ["afternoon", "evening"], "experience_years": 2, "phone": "021-23456789"},
    ],
    "Chengdu": [
        {"service_id": "svc_cd_001", "name": "Swan Home Wuhou", "service_type": "cleaning", "rating": 4.6, "price_per_hour": 45, "available_time": ["morning", "afternoon"], "experience_years": 3, "phone": "028-12345678"},
    ],
    "Guangzhou": [
        {"service_id": "svc_gz_001", "name": "58 Home Tianhe", "service_type": "cleaning", "rating": 4.7, "price_per_hour": 55, "available_time": ["morning", "afternoon", "evening"], "experience_years": 4, "phone": "020-12345678"},
        {"service_id": "svc_gz_002", "name": "Anyi Home Yuexiu", "service_type": "nanny", "rating": 4.8, "price_per_day": 320, "available_time": ["all day"], "experience_years": 6, "phone": "020-23456789"},
    ],
    "Shenzhen": [
        {"service_id": "svc_sz_001", "name": "Homey Nanshan", "service_type": "cleaning", "rating": 4.6, "price_per_hour": 60, "available_time": ["morning", "afternoon"], "experience_years": 3, "phone": "0755-12345678"},
        {"service_id": "svc_sz_002", "name": "Baby Care Futian", "service_type": "nanny", "rating": 4.9, "price_per_day": 380, "available_time": ["all day"], "experience_years": 7, "phone": "0755-23456789"},
    ],
    "Wuhan": [
        {"service_id": "svc_wh_001", "name": "Clean Home Guanggu", "service_type": "cleaning", "rating": 4.5, "price_per_hour": 40, "available_time": ["morning", "afternoon"], "experience_years": 2, "phone": "027-12345678"},
    ],
    "Nanjing": [
        {"service_id": "svc_nj_001", "name": "Xin Fu Home Xinjiekou", "service_type": "cleaning", "rating": 4.7, "price_per_hour": 50, "available_time": ["morning", "afternoon", "evening"], "experience_years": 4, "phone": "025-12345678"},
    ],
    "Chongqing": [
        {"service_id": "svc_cq_001", "name": "Jie Ba Shi Jiefangbei", "service_type": "cleaning", "rating": 4.6, "price_per_hour": 45, "available_time": ["morning", "afternoon"], "experience_years": 3, "phone": "023-12345678"},
    ],
    "Suzhou": [
        {"service_id": "svc_su_001", "name": "Suzhou Home Care", "service_type": "cleaning", "rating": 4.6, "price_per_hour": 48, "available_time": ["morning", "afternoon"], "experience_years": 3, "phone": "0512-12345678"},
    ],
}

PACKAGES = {
    "SF1234567890": {
        "company": "SF Express", "status": "In Transit",
        "history": [
            {"time": "2024-02-14 10:00", "location": "Beijing Distribution Center", "status": "Shipped"},
            {"time": "2024-02-14 18:00", "location": "Shanghai Distribution Center", "status": "Arrived"},
            {"time": "2024-02-15 08:00", "location": "Shanghai Pudong Station", "status": "Out for Delivery"},
        ]
    },
    "YT9876543210": {
        "company": "YTO Express", "status": "Delivered",
        "history": [
            {"time": "2024-02-13 14:00", "location": "Chengdu", "status": "Picked Up"},
            {"time": "2024-02-14 20:00", "location": "Chongqing", "status": "In Transit"},
            {"time": "2024-02-15 10:00", "location": "Chongqing Jiangbei", "status": "Delivered"},
        ]
    },
}

# ============ Entertainment ============

MOVIES = {
    "Beijing": [
        {"movie_id": "mov_bj_001", "name": "The Wandering Earth 3", "genre": "Sci-Fi", "duration": 150, "rating": 8.5, "cinemas": ["Wanda Cinema CBD", "CGV Xidan", "Bona International"], "showtimes": ["10:30", "13:20", "16:10", "19:00", "21:50"], "price": 45},
        {"movie_id": "mov_bj_002", "name": "YOLO", "genre": "Drama", "duration": 120, "rating": 7.8, "cinemas": ["Wanda Cinema CBD", "UME Cinema", "Bona International"], "showtimes": ["11:00", "14:30", "17:00", "20:30"], "price": 40},
        {"movie_id": "mov_bj_003", "name": "Article 20", "genre": "Drama", "duration": 110, "rating": 8.2, "cinemas": ["CGV Xidan", "UME Cinema", "Jackie Chan Cinema"], "showtimes": ["10:00", "13:00", "15:30", "18:00", "20:30"], "price": 38},
        {"movie_id": "mov_bj_004", "name": "Kung Fu Panda 4", "genre": "Animation", "duration": 95, "rating": 7.5, "cinemas": ["Wanda Cinema CBD", "CGV Xidan", "Bona International"], "showtimes": ["09:30", "11:30", "14:00", "16:30", "19:00"], "price": 35},
    ],
    "Shanghai": [
        {"movie_id": "mov_sh_001", "name": "The Wandering Earth 3", "genre": "Sci-Fi", "duration": 150, "rating": 8.5, "cinemas": ["Shanghai Film Center", "Grand Cinema", "Wanda Cinema Wujiaochang"], "showtimes": ["10:30", "13:20", "16:10", "19:00", "21:50"], "price": 50},
        {"movie_id": "mov_sh_002", "name": "YOLO", "genre": "Drama", "duration": 120, "rating": 7.8, "cinemas": ["Shanghai Film Center", "SFC Cinema", "Wanda Cinema Wujiaochang"], "showtimes": ["11:00", "14:30", "17:00", "20:30"], "price": 45},
        {"movie_id": "mov_sh_003", "name": "Dune 2", "genre": "Sci-Fi", "duration": 165, "rating": 8.8, "cinemas": ["Grand Cinema", "SFC Cinema", "CGV Longzhimeng"], "showtimes": ["10:00", "13:30", "17:00", "20:30"], "price": 55},
    ],
    "Chengdu": [
        {"movie_id": "mov_cd_001", "name": "The Wandering Earth 3", "genre": "Sci-Fi", "duration": 150, "rating": 8.5, "cinemas": ["Pacific Cinema", "Wanda Cinema Jinhua", "CGV Chunxi Road"], "showtimes": ["10:30", "13:20", "16:10", "19:00", "21:50"], "price": 42},
        {"movie_id": "mov_cd_002", "name": "YOLO", "genre": "Drama", "duration": 120, "rating": 7.8, "cinemas": ["Pacific Cinema", "Wanda Cinema Jinhua", "Emei 1958 Cinema"], "showtimes": ["11:00", "14:30", "17:00", "20:30"], "price": 38},
        {"movie_id": "mov_cd_003", "name": "Kung Fu Panda 4", "genre": "Animation", "duration": 95, "rating": 7.5, "cinemas": ["CGV Chunxi Road", "Emei 1958 Cinema", "Wanda Cinema Jinhua"], "showtimes": ["09:30", "11:30", "14:00", "16:30", "19:00"], "price": 32},
    ],
    "Guangzhou": [
        {"movie_id": "mov_gz_001", "name": "The Wandering Earth 3", "genre": "Sci-Fi", "duration": 150, "rating": 8.5, "cinemas": ["UA Taikoo Hui", "Jinyi Cinema Tianhe", "CGV Zhujiang New Town"], "showtimes": ["10:30", "13:20", "16:10", "19:00", "21:50"], "price": 48},
        {"movie_id": "mov_gz_002", "name": "Dune 2", "genre": "Sci-Fi", "duration": 165, "rating": 8.8, "cinemas": ["UA Taikoo Hui", "CGV Zhujiang New Town"], "showtimes": ["10:00", "13:30", "17:00", "20:30"], "price": 52},
    ],
    "Shenzhen": [
        {"movie_id": "mov_sz_001", "name": "The Wandering Earth 3", "genre": "Sci-Fi", "duration": 150, "rating": 8.5, "cinemas": ["Broadway Cinema Futian", "Emperor Cinema Coco Park", "CGV MixC"], "showtimes": ["10:30", "13:20", "16:10", "19:00", "21:50"], "price": 50},
        {"movie_id": "mov_sz_002", "name": "Kung Fu Panda 4", "genre": "Animation", "duration": 95, "rating": 7.5, "cinemas": ["Broadway Cinema Futian", "CGV MixC"], "showtimes": ["09:30", "11:30", "14:00", "16:30", "19:00"], "price": 38},
    ],
    "Wuhan": [
        {"movie_id": "mov_wh_001", "name": "The Wandering Earth 3", "genre": "Sci-Fi", "duration": 150, "rating": 8.5, "cinemas": ["Wanda Cinema Guanggu", "Jinyi Cinema Jianghan Road"], "showtimes": ["10:30", "13:20", "16:10", "19:00"], "price": 40},
        {"movie_id": "mov_wh_002", "name": "YOLO", "genre": "Drama", "duration": 120, "rating": 7.8, "cinemas": ["Wanda Cinema Guanggu", "Jinyi Cinema Jianghan Road"], "showtimes": ["11:00", "14:30", "17:00", "20:30"], "price": 36},
    ],
    "Nanjing": [
        {"movie_id": "mov_nj_001", "name": "The Wandering Earth 3", "genre": "Sci-Fi", "duration": 150, "rating": 8.5, "cinemas": ["Wanda Cinema Xinjiekou", "CGV Jinling"], "showtimes": ["10:30", "13:20", "16:10", "19:00"], "price": 42},
        {"movie_id": "mov_nj_002", "name": "Article 20", "genre": "Drama", "duration": 110, "rating": 8.2, "cinemas": ["Wanda Cinema Xinjiekou", "CGV Jinling"], "showtimes": ["10:00", "13:00", "15:30", "18:00"], "price": 38},
    ],
    "Chongqing": [
        {"movie_id": "mov_cq_001", "name": "The Wandering Earth 3", "genre": "Sci-Fi", "duration": 150, "rating": 8.5, "cinemas": ["Wanda Cinema Jiefangbei", "CGV Raffles City"], "showtimes": ["10:30", "13:20", "16:10", "19:00"], "price": 40},
        {"movie_id": "mov_cq_002", "name": "Kung Fu Panda 4", "genre": "Animation", "duration": 95, "rating": 7.5, "cinemas": ["Wanda Cinema Jiefangbei", "CGV Raffles City"], "showtimes": ["09:30", "11:30", "14:00", "16:30"], "price": 35},
    ],
    "Suzhou": [
        {"movie_id": "mov_su_001", "name": "The Wandering Earth 3", "genre": "Sci-Fi", "duration": 150, "rating": 8.5, "cinemas": ["Jinyi Cinema Suzhou Center", "Broadway Cinema Gusu"], "showtimes": ["10:30", "13:20", "16:10", "19:00"], "price": 42},
        {"movie_id": "mov_su_002", "name": "YOLO", "genre": "Drama", "duration": 120, "rating": 7.8, "cinemas": ["Jinyi Cinema Suzhou Center", "Broadway Cinema Gusu"], "showtimes": ["11:00", "14:30", "17:00", "20:30"], "price": 40},
    ],
}

SHOWS = {
    "Beijing": [
        {"show_id": "show_bj_001", "name": "Jay Chou Concert", "type": "Concert", "venue": "National Stadium Bird's Nest", "date": "2026-03-08", "time": "19:30", "duration": 180, "price_range": "480-1980", "available_zones": ["Floor", "Stand A", "Stand B", "Stand C"], "rating": 9.5},
        {"show_id": "show_bj_002", "name": "Erta Thunderstorm", "type": "Theater", "venue": "Capital Theatre", "date": "2026-03-15", "time": "19:30", "duration": 150, "price_range": "180-680", "available_zones": ["Orchestra", "First Floor", "Second Floor"], "rating": 8.8},
        {"show_id": "show_bj_003", "name": "National Centre Concert", "type": "Concert", "venue": "National Centre for the Performing Arts", "date": "2026-03-22", "time": "19:30", "duration": 120, "price_range": "280-880", "available_zones": ["Orchestra", "First Floor", "Second Floor"], "rating": 9.2},
    ],
    "Shanghai": [
        {"show_id": "show_sh_005", "name": "Eason Chan Concert", "type": "Concert", "venue": "Mercedes-Benz Arena", "date": "2026-03-08", "time": "19:30", "duration": 180, "price_range": "480-1880", "available_zones": ["Floor", "Stand A", "Stand B", "Stand C"], "rating": 9.4},
        {"show_id": "show_sh_006", "name": "G.E.M. Concert", "type": "Concert", "venue": "Shanghai Stadium", "date": "2026-03-08", "time": "19:00", "duration": 180, "price_range": "380-1580", "available_zones": ["Floor", "Stand A", "Stand B"], "rating": 9.2},
        {"show_id": "show_sh_001", "name": "Jay Chou Concert", "type": "Concert", "venue": "Shanghai Stadium", "date": "2026-03-10", "time": "19:30", "duration": 180, "price_range": "480-1980", "available_zones": ["Floor", "Stand A", "Stand B", "Stand C"], "rating": 9.5},
        {"show_id": "show_sh_002", "name": "Mayday Concert", "type": "Concert", "venue": "Shanghai Stadium", "date": "2026-03-11", "time": "19:00", "duration": 180, "price_range": "580-2280", "available_zones": ["Floor", "Stand A", "Stand B"], "rating": 9.6},
        {"show_id": "show_sh_004", "name": "JJ Lin Concert", "type": "Concert", "venue": "Mercedes-Benz Arena", "date": "2026-03-15", "time": "19:30", "duration": 180, "price_range": "380-1680", "available_zones": ["Floor", "Stand A", "Stand B", "Stand C"], "rating": 9.3},
        {"show_id": "show_sh_003", "name": "Secret Love in Peach Blossom Land", "type": "Theater", "venue": "Shanghai Grand Theatre", "date": "2026-03-18", "time": "19:30", "duration": 160, "price_range": "280-880", "available_zones": ["Orchestra", "First Floor", "Second Floor"], "rating": 9.0},
    ],
    "Chengdu": [
        {"show_id": "show_cd_001", "name": "Joker Xue Concert", "type": "Concert", "venue": "Chengdu Open Air Music Park", "date": "2026-03-12", "time": "19:30", "duration": 180, "price_range": "380-1580", "available_zones": ["Floor", "Stand A", "Stand B"], "rating": 9.1},
        {"show_id": "show_cd_002", "name": "Teahouse", "type": "Theater", "venue": "Jincheng Art Palace", "date": "2026-03-19", "time": "19:30", "duration": 145, "price_range": "180-580", "available_zones": ["VIP", "First Class", "Second Class"], "rating": 8.7},
    ],
    "Guangzhou": [
        {"show_id": "show_gz_001", "name": "Joker Xue Concert", "type": "Concert", "venue": "Guangzhou Tianhe Stadium", "date": "2026-04-05", "time": "19:30", "duration": 180, "price_range": "380-1580", "available_zones": ["Floor", "Stand A", "Stand B"], "rating": 9.1},
        {"show_id": "show_gz_002", "name": "Cantonese Opera Classics", "type": "Theater", "venue": "Guangzhou Opera House", "date": "2026-04-12", "time": "19:30", "duration": 150, "price_range": "180-680", "available_zones": ["Orchestra", "First Floor", "Second Floor"], "rating": 8.9},
    ],
    "Shenzhen": [
        {"show_id": "show_sz_001", "name": "Mayday Concert", "type": "Concert", "venue": "Shenzhen Bay Sports Center", "date": "2026-04-18", "time": "19:30", "duration": 180, "price_range": "480-1980", "available_zones": ["Floor", "Stand A", "Stand B", "Stand C"], "rating": 9.5},
        {"show_id": "show_sz_002", "name": "Tech Innovation Forum", "type": "Theater", "venue": "Shenzhen Poly Theater", "date": "2026-05-03", "time": "19:30", "duration": 120, "price_range": "280-680", "available_zones": ["VIP", "First Class", "Second Class"], "rating": 8.6},
    ],
    "Wuhan": [
        {"show_id": "show_wh_001", "name": "JJ Lin Concert", "type": "Concert", "venue": "Wuhan Sports Center", "date": "2026-04-22", "time": "19:30", "duration": 180, "price_range": "380-1680", "available_zones": ["Floor", "Stand A", "Stand B"], "rating": 9.3},
    ],
    "Nanjing": [
        {"show_id": "show_nj_001", "name": "Eason Chan Concert", "type": "Concert", "venue": "Nanjing Olympic Sports Center", "date": "2026-04-25", "time": "19:30", "duration": 180, "price_range": "480-1880", "available_zones": ["Floor", "Stand A", "Stand B"], "rating": 9.4},
        {"show_id": "show_nj_002", "name": "Peking Opera Collection", "type": "Theater", "venue": "Jiangsu Grand Theatre", "date": "2026-05-06", "time": "19:30", "duration": 140, "price_range": "180-580", "available_zones": ["Orchestra", "First Floor", "Second Floor"], "rating": 8.8},
    ],
    "Chongqing": [
        {"show_id": "show_cq_001", "name": "G.E.M. Concert", "type": "Concert", "venue": "Chongqing Olympic Sports Center", "date": "2026-05-09", "time": "19:00", "duration": 180, "price_range": "380-1580", "available_zones": ["Floor", "Stand A", "Stand B"], "rating": 9.2},
    ],
    "Suzhou": [
        {"show_id": "show_su_001", "name": "Kunqu Opera Peony Pavilion", "type": "Theater", "venue": "Suzhou Grand Theatre", "date": "2026-04-29", "time": "19:30", "duration": 160, "price_range": "180-880", "available_zones": ["Orchestra", "First Floor", "Second Floor"], "rating": 9.0},
    ],
}

SPORTS_EVENTS = {
    "Beijing": [
        {"event_id": "evt_bj_001", "name": "CBA Playoffs: Beijing Shougang vs Guangdong Tigers", "sport_type": "Basketball", "venue": "Cadillac Arena", "date": "2026-03-06", "time": "19:35", "home_team": "Beijing Shougang", "away_team": "Guangdong Tigers", "price_range": "180-1280", "available_zones": ["VIP", "Stand A", "Stand B", "Stand C"], "rating": 8.8},
        {"event_id": "evt_bj_002", "name": "CSL: Beijing Guoan vs Shanghai Shenhua", "sport_type": "Football", "venue": "Workers' Stadium", "date": "2026-03-01", "time": "19:30", "home_team": "Beijing Guoan", "away_team": "Shanghai Shenhua", "price_range": "120-680", "available_zones": ["Home Stand", "Away Stand", "Neutral Stand", "Regular Stand"], "rating": 8.5},
        {"event_id": "evt_bj_003", "name": "China Open Tennis", "sport_type": "Tennis", "venue": "National Tennis Center", "date": "2026-03-21", "time": "14:00", "home_team": None, "away_team": None, "price_range": "280-2880", "available_zones": ["Center Court", "Court 1", "Court 2"], "rating": 9.2},
    ],
    "Shanghai": [
        {"event_id": "evt_sh_001", "name": "CBA: Shanghai Sharks vs Liaoning Steelers", "sport_type": "Basketball", "venue": "Yuanshen Sports Center", "date": "2026-03-09", "time": "19:35", "home_team": "Shanghai Sharks", "away_team": "Liaoning Steelers", "price_range": "150-980", "available_zones": ["VIP", "Stand A", "Stand B"], "rating": 8.3},
        {"event_id": "evt_sh_002", "name": "CSL: Shanghai Port vs Shandong Taishan", "sport_type": "Football", "venue": "Shanghai Stadium", "date": "2026-03-16", "time": "19:30", "home_team": "Shanghai Port", "away_team": "Shandong Taishan", "price_range": "150-880", "available_zones": ["Home Stand", "Away Stand", "Neutral Stand"], "rating": 8.7},
    ],
    "Chengdu": [
        {"event_id": "evt_cd_001", "name": "CSL: Chengdu Rongcheng vs Beijing Guoan", "sport_type": "Football", "venue": "Phoenix Hill Sports Park", "date": "2026-03-10", "time": "19:30", "home_team": "Chengdu Rongcheng", "away_team": "Beijing Guoan", "price_range": "100-580", "available_zones": ["Home Stand", "Away Stand", "Neutral Stand"], "rating": 8.4},
    ],
}

# ============ Healthcare ============

DOCTORS = {
    "Beijing": [
        {"doctor_id": "doc_bj_001", "name": "Zhang Wei", "hospital": "Peking Union Medical College Hospital", "department": "Internal Medicine", "title": "Chief Physician", "specialty": "Cardiovascular Disease", "rating": 4.9, "experience_years": 20, "available_dates": ["2026-03-02", "2026-03-03", "2026-03-04"]},
        {"doctor_id": "doc_bj_002", "name": "Li Ming", "hospital": "Peking Union Medical College Hospital", "department": "Surgery", "title": "Associate Chief Physician", "specialty": "Orthopedic Surgery", "rating": 4.8, "experience_years": 15, "available_dates": ["2026-03-02", "2026-03-05"]},
        {"doctor_id": "doc_bj_003", "name": "Wang Fang", "hospital": "Peking University First Hospital", "department": "Pediatrics", "title": "Chief Physician", "specialty": "Pediatric Respiratory Disease", "rating": 4.7, "experience_years": 18, "available_dates": ["2026-03-03", "2026-03-04", "2026-03-06"]},
    ],
    "Shanghai": [
        {"doctor_id": "doc_sh_001", "name": "Chen Jing", "hospital": "Ruijin Hospital", "department": "Internal Medicine", "title": "Chief Physician", "specialty": "Digestive System Disease", "rating": 4.8, "experience_years": 22, "available_dates": ["2026-03-02", "2026-03-04"]},
        {"doctor_id": "doc_sh_002", "name": "Liu Yang", "hospital": "Huashan Hospital", "department": "Neurology", "title": "Associate Chief Physician", "specialty": "Nervous System Disease", "rating": 4.9, "experience_years": 16, "available_dates": ["2026-03-03", "2026-03-05"]},
    ],
    "Chengdu": [
        {"doctor_id": "doc_cd_001", "name": "Zhao Lei", "hospital": "West China Hospital", "department": "Internal Medicine", "title": "Chief Physician", "specialty": "Endocrine Disease", "rating": 4.8, "experience_years": 19, "available_dates": ["2026-03-02", "2026-03-03"]},
    ],
    "Guangzhou": [
        {"doctor_id": "doc_gz_001", "name": "Lin Hua", "hospital": "Sun Yat-sen Memorial Hospital", "department": "Internal Medicine", "title": "Chief Physician", "specialty": "Respiratory Disease", "rating": 4.8, "experience_years": 21, "available_dates": ["2026-03-15", "2026-04-05", "2026-04-10"]},
        {"doctor_id": "doc_gz_002", "name": "Guo Ping", "hospital": "Guangzhou First People's Hospital", "department": "Dermatology", "title": "Associate Chief Physician", "specialty": "Dermatology", "rating": 4.6, "experience_years": 14, "available_dates": ["2026-04-08", "2026-04-12"]},
    ],
    "Shenzhen": [
        {"doctor_id": "doc_sz_001", "name": "Wu Qiang", "hospital": "Shenzhen People's Hospital", "department": "Cardiology", "title": "Chief Physician", "specialty": "Cardiovascular Disease", "rating": 4.9, "experience_years": 20, "available_dates": ["2026-04-15", "2026-04-20", "2026-04-25"]},
        {"doctor_id": "doc_sz_002", "name": "He Ling", "hospital": "Shenzhen Children's Hospital", "department": "Pediatrics", "title": "Chief Physician", "specialty": "Pediatric Cardiology", "rating": 4.8, "experience_years": 17, "available_dates": ["2026-05-03", "2026-05-09"]},
    ],
    "Wuhan": [
        {"doctor_id": "doc_wh_001", "name": "Yao Jun", "hospital": "Tongji Hospital", "department": "Surgery", "title": "Chief Physician", "specialty": "General Surgery", "rating": 4.9, "experience_years": 23, "available_dates": ["2026-04-18", "2026-04-22"]},
    ],
    "Nanjing": [
        {"doctor_id": "doc_nj_001", "name": "Fang Ming", "hospital": "Jiangsu Province Hospital", "department": "Neurology", "title": "Chief Physician", "specialty": "Cerebrovascular Disease", "rating": 4.8, "experience_years": 22, "available_dates": ["2026-04-25", "2026-05-06"]},
    ],
    "Chongqing": [
        {"doctor_id": "doc_cq_001", "name": "Peng Hui", "hospital": "The First Affiliated Hospital of Chongqing Medical University", "department": "Internal Medicine", "title": "Chief Physician", "specialty": "Gastroenterology", "rating": 4.7, "experience_years": 18, "available_dates": ["2026-05-09", "2026-05-15"]},
    ],
    "Suzhou": [
        {"doctor_id": "doc_su_001", "name": "Shen Yuan", "hospital": "The First Affiliated Hospital of Soochow University", "department": "Dermatology", "title": "Associate Chief Physician", "specialty": "Dermatology", "rating": 4.6, "experience_years": 13, "available_dates": ["2026-04-29", "2026-05-12"]},
    ],
}

MEDICINES = [
    {"name": "Amoxicillin Capsules", "category": "Antibiotic", "manufacturer": "North China Pharmaceutical", "specification": "0.25g*24 capsules", "price": 15.80, "indications": "For respiratory infections, urinary tract infections, skin and soft tissue infections caused by sensitive bacteria", "contraindications": "Contraindicated in patients allergic to penicillin drugs", "side_effects": "May cause nausea, vomiting, diarrhea and other gastrointestinal reactions", "dosage": "Adults: 0.5g per dose, every 6-8 hours", "prescription_required": True},
    {"name": "Ibuprofen Extended-Release Capsules", "category": "Analgesic", "manufacturer": "SmithKline", "specification": "0.3g*20 capsules", "price": 18.50, "indications": "For mild to moderate pain such as headache, joint pain, migraine, toothache, muscle pain, neuralgia, dysmenorrhea", "contraindications": "Contraindicated in patients allergic to this product and those with peptic ulcer", "side_effects": "May cause nausea, vomiting, heartburn or mild indigestion", "dosage": "Adults: 0.3g per dose, twice daily", "prescription_required": False},
    {"name": "Cold Relief Granules", "category": "Cold Medicine", "manufacturer": "999 Pharmaceutical", "specification": "10g*9 sachets", "price": 12.00, "indications": "For headache, fever, nasal congestion, runny nose, sore throat and other cold symptoms", "contraindications": "Pregnant and lactating women should use with caution", "side_effects": "Occasionally rash, nausea, vomiting, abdominal pain", "dosage": "Dissolve in hot water, 10g per dose, three times daily", "prescription_required": False},
    {"name": "Compound Licorice Tablets", "category": "Cough Medicine", "manufacturer": "Taiji Group", "specification": "100 tablets", "price": 8.50, "indications": "For cough relief and expectorant", "contraindications": "Contraindicated in pregnant and lactating women", "side_effects": "May cause nausea, vomiting, constipation", "dosage": "Oral, 3-4 tablets per dose, three times daily", "prescription_required": False},
    {"name": "Antihypertensive No.0", "category": "Antihypertensive", "manufacturer": "Beijing Antihypertensive Pharmaceutical", "specification": "100 tablets", "price": 25.00, "indications": "For hypertension", "contraindications": "Contraindicated in patients with hypotension", "side_effects": "May cause dizziness, fatigue", "dosage": "Oral, 1-2 tablets per dose, three times daily", "prescription_required": True},
]

# ============ Financial ============

BILLS = [
    {"bill_id": "DL20260219001", "bill_type": "Electricity", "company": "State Grid", "account_number": "1234567890", "amount": 156.80, "due_date": "2026-03-09", "status": "Unpaid", "billing_period": "2026-01"},
    {"bill_id": "BILL20260215002", "bill_type": "Water", "company": "Water Company", "account_number": "9876543210", "amount": 45.20, "due_date": "2026-03-06", "status": "Unpaid", "billing_period": "2026-01"},
    {"bill_id": "BILL20260215003", "bill_type": "Gas", "company": "Gas Group", "account_number": "5555666677", "amount": 89.50, "due_date": "2026-03-14", "status": "Unpaid", "billing_period": "2026-01"},
    {"bill_id": "BILL20260115001", "bill_type": "Electricity", "company": "State Grid", "account_number": "1234567890", "amount": 142.30, "due_date": "2026-01-28", "status": "Paid", "billing_period": "2025-12", "payment_date": "2026-01-20"},
    {"bill_id": "BILL20260215004", "bill_type": "Internet", "company": "China Telecom", "account_number": "1111222233", "amount": 129.00, "due_date": "2026-03-02", "status": "Unpaid", "billing_period": "2026-02"},
]

BANK_ACCOUNTS = [
    {"account_id": "6222021234567890", "bank": "ICBC", "type": "Savings", "balance": 15680.50, "holder_name": "Zhang Wei", "status": "Active"},
    {"account_id": "6228480012345678", "bank": "ABC", "type": "Checking", "balance": 8920.00, "holder_name": "Zhang Wei", "status": "Active"},
    {"account_id": "6217001234567890", "bank": "CCB", "type": "Savings", "balance": 52300.80, "holder_name": "Li Ming", "status": "Active"},
]

TRANSACTIONS = [
    {"transaction_id": "TXN20260301001", "account_id": "6222021234567890", "type": "Transfer Out", "amount": 500.00, "balance_after": 15680.50, "counterparty": "Li Ming", "time": "2026-03-01 10:30:00", "note": "Lunch money"},
    {"transaction_id": "TXN20260228002", "account_id": "6222021234567890", "type": "Deposit", "amount": 8000.00, "balance_after": 16180.50, "counterparty": "Salary", "time": "2026-02-28 09:00:00", "note": "February salary"},
    {"transaction_id": "TXN20260227003", "account_id": "6222021234567890", "type": "Payment", "amount": 156.80, "balance_after": 8180.50, "counterparty": "State Grid", "time": "2026-02-27 14:20:00", "note": "Electricity bill"},
    {"transaction_id": "TXN20260225004", "account_id": "6222021234567890", "type": "Transfer In", "amount": 1000.00, "balance_after": 8337.30, "counterparty": "Wang Fang", "time": "2026-02-25 16:45:00", "note": "Repayment"},
    {"transaction_id": "TXN20260220005", "account_id": "6228480012345678", "type": "Withdrawal", "amount": 2000.00, "balance_after": 8920.00, "counterparty": "ATM", "time": "2026-02-20 11:00:00", "note": "Cash withdrawal"},
]

# ============ Education ============

COURSES = [
    {"course_id": "CS101", "name": "Python Programming Basics", "category": "Programming", "instructor": "Mr. Zhang", "duration": "8 weeks", "schedule": "Tue, Thu 19:00-21:00", "price": 1980.00, "capacity": 30, "enrolled": 25, "rating": 4.8, "level": "Beginner", "start_date": "2026-03-15"},
    {"course_id": "CS201", "name": "Data Structures and Algorithms", "category": "Programming", "instructor": "Mr. Li", "duration": "12 weeks", "schedule": "Wed, Fri 19:00-21:00", "price": 2980.00, "capacity": 25, "enrolled": 20, "rating": 4.9, "level": "Intermediate", "start_date": "2026-03-22"},
    {"course_id": "DS101", "name": "Data Science Fundamentals", "category": "Programming", "instructor": "Ms. Li", "duration": "10 weeks", "schedule": "Mon, Wed 19:00-21:00", "price": 2580.00, "capacity": 20, "enrolled": 15, "rating": 4.7, "level": "Intermediate", "start_date": "2026-03-20"},
    {"course_id": "EN101", "name": "Business English Speaking", "category": "Language", "instructor": "Ms. Wang", "duration": "10 weeks", "schedule": "Mon, Wed 18:30-20:30", "price": 2280.00, "capacity": 20, "enrolled": 18, "rating": 4.7, "level": "Intermediate", "start_date": "2026-03-29"},
    {"course_id": "ART101", "name": "Drawing Fundamentals", "category": "Art", "instructor": "Mr. Zhao", "duration": "6 weeks", "schedule": "Sat 14:00-17:00", "price": 1580.00, "capacity": 15, "enrolled": 12, "rating": 4.6, "level": "Beginner", "start_date": "2026-04-05"},
    {"course_id": "MUS101", "name": "Guitar for Beginners", "category": "Music", "instructor": "Mr. Liu", "duration": "8 weeks", "schedule": "Sun 10:00-12:00", "price": 1880.00, "capacity": 12, "enrolled": 10, "rating": 4.8, "level": "Beginner", "start_date": "2026-04-12"},
]

BOOKS = [
    {"book_id": "ISBN9787115583949", "title": "Python Crash Course", "author": "Eric Matthes", "publisher": "Posts & Telecom Press", "category": "Computer Science", "location": "Area A, Floor 3", "call_number": "TP311.56/M123", "total_copies": 5, "available_copies": 2, "status": "Available"},
    {"book_id": "ISBN9787111544937", "title": "Computer Systems: A Programmer's Perspective", "author": "Randal E. Bryant", "publisher": "Machinery Industry Press", "category": "Computer Science", "location": "Area A, Floor 3", "call_number": "TP3/B456", "total_copies": 3, "available_copies": 0, "status": "Borrowed"},
    {"book_id": "Deep Learning", "title": "Deep Learning", "author": "Ian Goodfellow", "publisher": "MIT Press", "category": "Computer Science", "location": "Area A, Floor 3", "call_number": "TP18/G789", "total_copies": 4, "available_copies": 1, "status": "Available"},
    {"book_id": "ISBN9787020008735", "title": "To Live", "author": "Yu Hua", "publisher": "Writers Publishing House", "category": "Literature", "location": "Area B, Floor 2", "call_number": "I247.57/Y123", "total_copies": 8, "available_copies": 5, "status": "Available"},
    {"book_id": "ISBN9787544270878", "title": "The Three-Body Problem", "author": "Liu Cixin", "publisher": "Chongqing Publishing House", "category": "Science Fiction", "location": "Area B, Floor 2", "call_number": "I247.55/L234", "total_copies": 10, "available_copies": 3, "status": "Available"},
    {"book_id": "ISBN9787508660752", "title": "Sapiens: A Brief History of Humankind", "author": "Yuval Noah Harari", "publisher": "CITIC Press", "category": "History", "location": "Area C, Floor 1", "call_number": "K109/H345", "total_copies": 6, "available_copies": 1, "status": "Available"},
]

BORROWED_BOOKS = [
    {"borrow_id": "BRW20260215001", "book_id": "ISBN9787115583949", "title": "Python Crash Course", "borrower_name": "Zhang Wei", "borrow_date": "2026-02-15", "due_date": "2026-03-15", "status": "Borrowed", "renewals": 0, "max_renewals": 2},
    {"borrow_id": "BRW20260210002", "book_id": "ISBN9787544270878", "title": "The Three-Body Problem", "borrower_name": "Zhang Wei", "borrow_date": "2026-02-10", "due_date": "2026-03-10", "status": "Borrowed", "renewals": 1, "max_renewals": 2},
    {"borrow_id": "BRW20260220003", "book_id": "ISBN9787020008735", "title": "To Live", "borrower_name": "Li Ming", "borrow_date": "2026-02-20", "due_date": "2026-03-20", "status": "Borrowed", "renewals": 0, "max_renewals": 2},
]

# ============ Transportation ============

PARKING_LOTS = {
    "Beijing": [
        {"parking_id": "park_bj_001", "name": "China World Trade Center Parking", "address": "1 Jianguomenwai Avenue, CBD, Chaoyang District, Beijing", "total_spots": 500, "available_spots": 120, "price_per_hour": 10, "daily_max": 80, "spot_types": ["Regular", "EV Charging"], "operating_hours": "24 hours", "distance": 0.5, "rating": 4.5},
        {"parking_id": "park_bj_002", "name": "Kerry Centre Parking", "address": "1 Guanghua Road, CBD, Chaoyang District, Beijing", "total_spots": 350, "available_spots": 80, "price_per_hour": 8, "daily_max": 60, "spot_types": ["Regular", "EV Charging"], "operating_hours": "24 hours", "distance": 0.8, "rating": 4.4},
        {"parking_id": "park_bj_003", "name": "Sanlitun SOHO Parking", "address": "8 Gongti North Road, Chaoyang District, Beijing", "total_spots": 300, "available_spots": 45, "price_per_hour": 12, "daily_max": 100, "spot_types": ["Regular", "EV Charging", "Oversized"], "operating_hours": "24 hours", "distance": 1.2, "rating": 4.3},
        {"parking_id": "park_bj_004", "name": "Zhongguancun Plaza Parking", "address": "1 Zhongguancun Street, Haidian District, Beijing", "total_spots": 400, "available_spots": 200, "price_per_hour": 8, "daily_max": 60, "spot_types": ["Regular", "EV Charging"], "operating_hours": "24 hours", "distance": 0.3, "rating": 4.6},
    ],
    "Shanghai": [
        {"parking_id": "park_sh_001", "name": "Lujiazui IFC Parking", "address": "100 Century Avenue, Pudong, Shanghai", "total_spots": 600, "available_spots": 80, "price_per_hour": 15, "daily_max": 120, "spot_types": ["Regular", "EV Charging", "VIP"], "operating_hours": "24 hours", "distance": 0.8, "rating": 4.7},
        {"parking_id": "park_sh_002", "name": "Xujiahui Grand Gateway Parking", "address": "1 Hongqiao Road, Xuhui District, Shanghai", "total_spots": 350, "available_spots": 150, "price_per_hour": 10, "daily_max": 80, "spot_types": ["Regular", "EV Charging"], "operating_hours": "24 hours", "distance": 0.4, "rating": 4.4},
    ],
    "Chengdu": [
        {"parking_id": "park_cd_001", "name": "Chunxi Road IFS Parking", "address": "1 Hongxing Road Section 3, Jinjiang District, Chengdu", "total_spots": 450, "available_spots": 100, "price_per_hour": 8, "daily_max": 60, "spot_types": ["Regular", "EV Charging"], "operating_hours": "24 hours", "distance": 0.6, "rating": 4.5},
    ],
}

RIDE_STATUSES = {
    "RIDE123456": {
        "ride_id": "RIDE123456",
        "status": "Driver Arrived",
        "driver_name": "Driver Wang",
        "driver_phone": "138****1234",
        "car_plate": "Beijing A12345",
        "car_type": "comfort",
        "pickup_location": "China World Trade Center, Chaoyang, Beijing",
        "dropoff_location": "Zhongguancun, Haidian, Beijing",
        "estimated_arrival": "2 minutes",
        "current_location": "200 meters from pickup point",
    },
    "RIDE789012": {
        "ride_id": "RIDE789012",
        "status": "In Progress",
        "driver_name": "Driver Li",
        "driver_phone": "139****5678",
        "car_plate": "Beijing B67890",
        "car_type": "economy",
        "pickup_location": "Lujiazui, Pudong, Shanghai",
        "dropoff_location": "Xujiahui, Xuhui, Shanghai",
        "estimated_arrival": "15 minutes",
        "current_location": "5 km traveled",
    },
}

# Car types for ride hailing
CAR_TYPES = {
    "economy": {"base_price": 15, "name": "Economy"},
    "comfort": {"base_price": 25, "name": "Comfort"},
    "business": {"base_price": 40, "name": "Business"},
    "luxury": {"base_price": 60, "name": "Luxury"},
}


# ============ Helper Functions ============

def get_mock_data_for_tools(tool_names: list) -> dict:
    """
    Get relevant mock data for a list of tool names.
    Used by generate_from_seeds.py to provide context to LLM.
    """
    tool_to_data = {
        "search_flights": {"flights": FLIGHTS},
        "book_flight": {"flights": FLIGHTS},
        "search_trains": {"trains": TRAINS},
        "book_train": {"trains": TRAINS},
        "search_hotels": {"hotels": HOTELS},
        "book_hotel": {"hotels": HOTELS},
        "search_cars": {"rental_cars": RENTAL_CARS},
        "book_car": {"rental_cars": RENTAL_CARS},
        "search_restaurants": {"restaurants": RESTAURANTS},
        "book_restaurant": {"restaurants": RESTAURANTS},
        "search_attractions": {"attractions": ATTRACTIONS},
        "book_attraction_ticket": {"attractions": ATTRACTIONS},
        "search_restaurants_delivery": {"delivery_restaurants": DELIVERY_RESTAURANTS},
        "place_food_order": {"delivery_restaurants": DELIVERY_RESTAURANTS},
        "search_home_services": {"home_services": HOME_SERVICES},
        "book_home_service": {"home_services": HOME_SERVICES},
        "track_package": {"packages": PACKAGES},
        "search_movies": {"movies": MOVIES},
        "book_movie_ticket": {"movies": MOVIES},
        "search_shows": {"shows": SHOWS},
        "book_show_ticket": {"shows": SHOWS},
        "search_sports_events": {"sports_events": SPORTS_EVENTS},
        "book_sports_ticket": {"sports_events": SPORTS_EVENTS},
        "search_doctors": {"doctors": DOCTORS},
        "book_appointment": {"doctors": DOCTORS},
        "search_medicine": {"medicines": MEDICINES},
        "list_bills": {"bills": BILLS},
        "pay_bill": {"bills": BILLS},
        "search_courses": {"courses": COURSES},
        "enroll_course": {"courses": COURSES},
        "search_books": {"books": BOOKS},
        "reserve_book": {"books": BOOKS},
        "search_parking": {"parking_lots": PARKING_LOTS},
        "reserve_parking_spot": {"parking_lots": PARKING_LOTS},
        "request_ride": {"car_types": CAR_TYPES},
        "check_ride_status": {"ride_statuses": RIDE_STATUSES},
        "cancel_ride": {"ride_statuses": RIDE_STATUSES},
        "check_balance": {"bank_accounts": BANK_ACCOUNTS},
        "transfer_money": {"bank_accounts": BANK_ACCOUNTS},
        "get_transaction_history": {"transactions": TRANSACTIONS, "bank_accounts": BANK_ACCOUNTS},
        "renew_book": {"borrowed_books": BORROWED_BOOKS},
    }

    result = {}
    for tool_name in tool_names:
        if tool_name in tool_to_data:
            result.update(tool_to_data[tool_name])
    return result


# ============ Common Constants ============

# 日期列表（用于任务生成）— 扩 2026-03/04/05 三个月窗口，避免月份单一
DATES = [
    # March 2026
    "2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05", "2026-03-06",
    "2026-03-10", "2026-03-11", "2026-03-12", "2026-03-13", "2026-03-14",
    "2026-03-15", "2026-03-16", "2026-03-17", "2026-03-18", "2026-03-19",
    "2026-03-20", "2026-03-21", "2026-03-22", "2026-03-23", "2026-03-24",
    "2026-03-25", "2026-03-26", "2026-03-27",
    # April 2026
    "2026-04-02", "2026-04-05", "2026-04-08", "2026-04-10", "2026-04-12",
    "2026-04-15", "2026-04-18", "2026-04-20", "2026-04-22", "2026-04-25",
    "2026-04-27", "2026-04-29",
    # May 2026
    "2026-05-03", "2026-05-06", "2026-05-09", "2026-05-12", "2026-05-15",
    "2026-05-18", "2026-05-21", "2026-05-24", "2026-05-27", "2026-05-30",
]

# 时间列表（用于任务生成）— 扩到覆盖全天
TIMES = [
    "09:00", "10:00", "11:00", "12:00", "13:00",
    "14:00", "15:00", "16:00", "17:00", "18:00",
    "19:00", "20:00", "21:00",
]

# 姓名列表（用于任务生成）— 扩到 40，英文 + 中文拼音混合
NAMES = [
    # Original 11
    "John Smith", "Mike Davis", "Sarah Chen", "Emily Wang", "David Liu",
    "Zhang Wei", "Li Na", "Wang Fang", "Liu Yang", "Chen Ming", "Zhou Jun",
    # English names (ASR-friendly)
    "Olivia Brown", "Noah Wilson", "Emma Taylor", "Aiden Miller", "Sophia Garcia",
    "Lucas Martinez", "Mia Anderson", "Ethan Thomas", "Isabella Jackson", "Mason White",
    # Pinyin names (retain ASR challenge)
    "Zhao Min", "Sun Lei", "Xu Jing", "Huang Tao", "Wu Qian",
    "Yang Yu", "Ma Liang", "Gao Yan", "Hu Bin", "Feng Jie",
    "Deng Hui", "Cao Yun", "Xie Peng", "Song Qi", "He Xia",
    "Lin Bo", "Tang Xue", "Luo Fei", "Qiu Lan",
]

PHONES = [
    # Original 12
    "13812345678", "13898765432", "13856781234", "13867894321",
    "13845678901", "13830018365", "13877949128", "13892862812",
    "13851574217", "13864788741", "13822970109", "13813897597",
    # Additional 12
    "13811223344", "13855667788", "13833445566", "13899887766",
    "13844556677", "13866778899", "13888990011", "13822334455",
    "13877665544", "13800112233", "13855443322", "13898776655",
]

ID_NUMBERS = [
    "110101199001011234", "310115198805062345", "510107199203153456",
    "440106199512044567", "330102199708085678", "610104199404096789",
]

ADDRESSES = [
    "Room 301, Building A, Central Apartment",
    "Room 502, Building B, East Apartment",
    "Room 203, Building C, West Apartment",
    "Room 801, Building A, North Apartment",
    "Room 106, Building B, South Apartment",
    "Room 405, Tower 2, Riverside Garden",
    "Room 1208, Block D, Sunshine Plaza",
    "Room 703, Building E, Lakeview Residence",
    "Room 1602, Tower 1, Oak Tree Court",
    "Room 505, Block F, Maple Lane Apartment",
    "Room 209, Tower 3, Pearl Gardens",
    "Room 1101, Building G, Harbor View Residence",
    "Room 306, Block H, Green Valley Apartment",
    "Room 804, Tower 4, Jade Garden",
    "Room 1505, Building I, Silver Creek Residence",
]

LICENSE_PLATES = [
    "京A12345", "沪B67890", "粤C23456", "川D78901",
    "浙E34567", "苏F89012",
]

LOCATIONS = [
    "Central Gate, Mall", "East Gate, Station", "West Gate, Airport",
    "North Gate, Hospital", "South Gate, Park",
    "Hotel Lobby, Central District", "Office Tower, East District",
    "Home, West District", "School Gate, North District",
]

# ============================================================
# Expanded domain mock data (14-domain extension)
# ============================================================

PRODUCTS = [
    {
        "product_id": "prd_001",
        "name": "Noise-Canceling Headphones",
        "category": "Electronics",
        "brand": "SoundMax",
        "price": 899.0,
        "rating": 4.7,
        "stock": 32,
        "return_policy": "7-day no-reason return, 30-day warranty service",
    },
    {
        "product_id": "prd_002",
        "name": "Lightweight Running Shoes",
        "category": "Sports",
        "brand": "RunPeak",
        "price": 499.0,
        "rating": 4.6,
        "stock": 45,
        "return_policy": "7-day return if unworn with original packaging",
    },
    {
        "product_id": "prd_003",
        "name": "Ergonomic Office Chair",
        "category": "Home",
        "brand": "WorkWell",
        "price": 1299.0,
        "rating": 4.8,
        "stock": 18,
        "return_policy": "15-day return, assembly fee not refundable",
    },
    {
        "product_id": "prd_004",
        "name": "Ceramic Cookware Set",
        "category": "Kitchen",
        "brand": "ChefHome",
        "price": 699.0,
        "rating": 4.5,
        "stock": 24,
        "return_policy": "7-day return if unused",
    },
]

SHOPPING_ORDERS = {
    "ord_1001": {
        "order_id": "ord_1001",
        "product_id": "prd_001",
        "status": "Shipped",
        "carrier": "SF Express",
        "eta": "2026-03-18",
    },
    "ord_1002": {
        "order_id": "ord_1002",
        "product_id": "prd_003",
        "status": "Processing",
        "carrier": "JD Logistics",
        "eta": "2026-03-20",
    },
}

CALENDAR_EVENTS = [
    {
        "event_id": "evt_001",
        "title": "Product review",
        "date": "2026-03-18",
        "start_time": "10:00",
        "end_time": "11:00",
        "location": "Meeting Room A",
    },
    {
        "event_id": "evt_002",
        "title": "Doctor follow-up",
        "date": "2026-03-19",
        "start_time": "15:00",
        "end_time": "15:30",
        "location": "City Hospital",
    },
    {
        "event_id": "evt_003",
        "title": "Team sync",
        "date": "2026-03-20",
        "start_time": "09:30",
        "end_time": "10:00",
        "location": "Online",
    },
]

CONTACTS = [
    {"contact_id": "ct_001", "name": "Li Na", "phone": "13811223344", "email": "lina@example.com"},
    {"contact_id": "ct_002", "name": "Zhang Wei", "phone": "13855667788", "email": "zhangwei@example.com"},
    {"contact_id": "ct_003", "name": "Sarah Chen", "phone": "13833445566", "email": "sarah.chen@example.com"},
    {"contact_id": "ct_004", "name": "David Liu", "phone": "13899887766", "email": "david.liu@example.com"},
]

RENTAL_LISTINGS = [
    {
        "listing_id": "rent_001",
        "title": "One-bedroom near Central Park",
        "city": "Beijing",
        "district": "Chaoyang",
        "monthly_rent": 6800.0,
        "bedrooms": 1,
        "agent_id": "agent_001",
        "address": "88 Park Road",
    },
    {
        "listing_id": "rent_002",
        "title": "Two-bedroom family apartment",
        "city": "Shanghai",
        "district": "Xuhui",
        "monthly_rent": 9200.0,
        "bedrooms": 2,
        "agent_id": "agent_002",
        "address": "16 Maple Street",
    },
    {
        "listing_id": "rent_003",
        "title": "Studio close to tech park",
        "city": "Shenzhen",
        "district": "Nanshan",
        "monthly_rent": 5600.0,
        "bedrooms": 1,
        "agent_id": "agent_003",
        "address": "5 Innovation Avenue",
    },
]

RENTAL_AGENTS = [
    {"agent_id": "agent_001", "name": "Wang Fang", "city": "Beijing", "phone": "13844556677"},
    {"agent_id": "agent_002", "name": "Mike Davis", "city": "Shanghai", "phone": "13866778899"},
    {"agent_id": "agent_003", "name": "Chen Ming", "city": "Shenzhen", "phone": "13888990011"},
]

JOBS = [
    {
        "job_id": "job_001",
        "title": "Machine Learning Engineer",
        "company": "FutureAI",
        "city": "Beijing",
        "job_type": "Full-time",
        "salary_range": "35k-55k",
        "status": "Open",
    },
    {
        "job_id": "job_002",
        "title": "Product Manager",
        "company": "CloudBridge",
        "city": "Shanghai",
        "job_type": "Full-time",
        "salary_range": "30k-45k",
        "status": "Open",
    },
    {
        "job_id": "job_003",
        "title": "Data Analyst",
        "company": "RetailPlus",
        "city": "Shenzhen",
        "job_type": "Contract",
        "salary_range": "20k-30k",
        "status": "Open",
    },
]

JOB_APPLICATIONS = {
    "app_1001": {
        "application_id": "app_1001",
        "job_id": "job_001",
        "candidate_name": "Li Na",
        "status": "Resume reviewed",
    },
    "app_1002": {
        "application_id": "app_1002",
        "job_id": "job_002",
        "candidate_name": "Zhang Wei",
        "status": "Interview scheduled",
    },
}

SERVICE_CENTERS = [
    {
        "center_id": "svc_001",
        "name": "Chaoyang Civic Service Center",
        "city": "Beijing",
        "service_type": "ID renewal",
        "address": "12 Civic Road",
        "available_dates": ["2026-03-18", "2026-03-20"],
        "required_documents": ["ID card", "Photo receipt", "Application form"],
    },
    {
        "center_id": "svc_002",
        "name": "Xuhui Public Service Hall",
        "city": "Shanghai",
        "service_type": "Residence permit",
        "address": "8 Service Avenue",
        "available_dates": ["2026-03-19", "2026-03-21"],
        "required_documents": ["Passport", "Lease contract", "Work certificate"],
    },
    {
        "center_id": "svc_003",
        "name": "Nanshan Administrative Center",
        "city": "Shenzhen",
        "service_type": "Business license",
        "address": "99 Innovation Road",
        "available_dates": ["2026-03-22", "2026-03-24"],
        "required_documents": ["Company name approval", "Owner ID", "Office lease"],
    },
]

CIVIC_APPLICATIONS = {
    "civ_1001": {"application_id": "civ_1001", "service_type": "ID renewal", "status": "Ready for pickup"},
    "civ_1002": {"application_id": "civ_1002", "service_type": "Residence permit", "status": "Under review"},
}

MOBILE_PLANS = [
    {
        "plan_id": "plan_001",
        "name": "Light Data 20GB",
        "carrier": "China Mobile",
        "monthly_fee": 79.0,
        "data_gb": 20,
        "minutes": 300,
    },
    {
        "plan_id": "plan_002",
        "name": "Family Share 80GB",
        "carrier": "China Unicom",
        "monthly_fee": 169.0,
        "data_gb": 80,
        "minutes": 1000,
    },
    {
        "plan_id": "plan_003",
        "name": "Unlimited Plus",
        "carrier": "China Telecom",
        "monthly_fee": 229.0,
        "data_gb": 120,
        "minutes": 2000,
    },
]

TELECOM_ACCOUNTS = {
    "13811223344": {
        "phone_number": "13811223344",
        "current_plan_id": "plan_001",
        "data_used_gb": 12.4,
        "billing_amount": 79.0,
        "billing_status": "Unpaid",
    },
    "13855667788": {
        "phone_number": "13855667788",
        "current_plan_id": "plan_002",
        "data_used_gb": 52.8,
        "billing_amount": 169.0,
        "billing_status": "Unpaid",
    },
}

REMINDERS = [
    {"reminder_id": "rem_001", "title": "Pay electricity bill", "due_time": "2026-03-18 09:00", "status": "Pending"},
    {"reminder_id": "rem_002", "title": "Call landlord", "due_time": "2026-03-19 18:00", "status": "Pending"},
]

NOTES = [
    {"note_id": "note_001", "title": "Apartment checklist", "content": "Check lighting, water pressure, and commute time."},
    {"note_id": "note_002", "title": "Gift ideas", "content": "Headphones, running shoes, cookware set."},
]
