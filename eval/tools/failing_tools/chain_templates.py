"""
Chain templates for multi-step tool use benchmark.

Each template defines:
  - chain: ordered list of tool calls
  - param_flow: maps "tool.param" to the source — either a previous tool's return
                 field path or a literal value from the user
  - user_params: params the user provides via speech (used for transcript generation)
  - description: human-readable scenario description

param_flow values:
  - {"from_tool": "func_name", "field": "path.to.field", "index": 0}
    → extract from previous tool's raw_output
  - "user"
    → value comes from user speech
  - {"literal": value}
    → fixed value (dates, booleans, etc.)

field path notation:
  - "restaurant_id"           → result["restaurant_id"] or result[index]["restaurant_id"]
  - "address[0].address_id"   → result["address"][0]["address_id"]
  - "$"                       → the result itself (when return type is bare str)
"""

CHAIN_TEMPLATES = {

    # ================================================================
    # UberEats — 5-step order flow
    # ================================================================
    "uber_eats": {
        "order_and_track_5": {
            "description": "Search restaurant, view menu, get profile, place order, track order",
            "chain": ["search_restaurants", "get_menu", "get_profile", "place_order", "track_order"],
            "param_flow": {
                "get_menu.restaurant_id": {"from_tool": "search_restaurants", "field": "restaurant_id", "index": 0},
                "place_order.restaurant_id": {"from_tool": "search_restaurants", "field": "restaurant_id", "index": 0},
                "place_order.items": {"composite": "order_items", "item_id_from": {"from_tool": "get_menu", "field": "item_id", "index": 0}, "quantity_from": "user"},
                "place_order.delivery_address_id": {"from_tool": "get_profile", "field": "address[0].address_id"},
                "place_order.payment_method_id": {"from_tool": "get_profile", "field": "payment_method[0].method_id"},
                "track_order.order_id": {"from_tool": "place_order", "field": "$"},
            },
            "user_params": {
                "search_restaurants.category": {"type": "choice", "values": ["Thai", "Mexican", "Indian", "Chinese", "Japanese", "Italian", "American", "Korean"]},
                "place_order.items.quantity": {"type": "int", "range": [1, 3]},
            },
        },
        "order_and_track_6": {
            "description": "Search, menu, profile, offers, place order, track",
            "chain": ["search_restaurants", "get_menu", "get_profile", "get_available_offers", "place_order", "track_order"],
            "param_flow": {
                "get_menu.restaurant_id": {"from_tool": "search_restaurants", "field": "restaurant_id", "index": 0},
                "place_order.restaurant_id": {"from_tool": "search_restaurants", "field": "restaurant_id", "index": 0},
                "place_order.items": {"composite": "order_items", "item_id_from": {"from_tool": "get_menu", "field": "item_id", "index": 0}, "quantity_from": "user"},
                "place_order.delivery_address_id": {"from_tool": "get_profile", "field": "address[0].address_id"},
                "place_order.payment_method_id": {"from_tool": "get_profile", "field": "payment_method[0].method_id"},
                "place_order.offer_id": {"from_tool": "get_available_offers", "field": "offer_id", "index": 0},
                "track_order.order_id": {"from_tool": "place_order", "field": "$"},
            },
            "user_params": {
                "search_restaurants.category": {"type": "choice", "values": ["Thai", "Mexican", "Indian", "Chinese"]},
                "place_order.items.quantity": {"type": "int", "range": [2, 3]},
            },
        },
    },

    # ================================================================
    # Amazon — 5 to 8 step purchase flow
    # ================================================================
    "amazon": {
        "search_and_buy_5": {
            "description": "Search product, view details, add to cart, place order, track shipment",
            "chain": ["search_products", "get_product_details", "add_to_cart", "place_order", "track_shipment"],
            "param_flow": {
                "get_product_details.product_id": {"from_tool": "search_products", "field": "product_id", "index": 0},
                "add_to_cart.product_id": {"from_tool": "search_products", "field": "product_id", "index": 0},
                "add_to_cart.variant_id": {"from_tool": "get_product_details", "field": "variations[0].variant_id"},
                "add_to_cart.quantity": "user",
                "place_order.address_id": {"from_tool": "list_addresses", "field": "address_id", "index": 0, "implicit": True},
                "place_order.payment_method_id": {"from_tool": "list_payment_methods", "field": "payment_method_id", "index": 0, "implicit": True},
                "track_shipment.order_id": {"from_tool": "place_order", "field": "$"},
            },
            "user_params": {
                "search_products.query": {"type": "choice", "values": ["headphones", "Sony", "iPad", "Dyson", "vacuum"]},
                "add_to_cart.quantity": {"type": "int", "range": [1, 2]},
            },
        },
        "full_purchase_7": {
            "description": "Search, details, add to cart, list addresses, list payments, place order, get order details",
            "chain": ["search_products", "get_product_details", "add_to_cart", "list_addresses", "list_payment_methods", "place_order", "get_order_details"],
            "param_flow": {
                "get_product_details.product_id": {"from_tool": "search_products", "field": "product_id", "index": 0},
                "add_to_cart.product_id": {"from_tool": "search_products", "field": "product_id", "index": 0},
                "add_to_cart.variant_id": {"from_tool": "get_product_details", "field": "variations[0].variant_id"},
                "add_to_cart.quantity": "user",
                "place_order.address_id": {"from_tool": "list_addresses", "field": "address_id", "index": 0},
                "place_order.payment_method_id": {"from_tool": "list_payment_methods", "field": "payment_method_id", "index": 0},
                "get_order_details.order_id": {"from_tool": "place_order", "field": "$"},
            },
            "user_params": {
                "search_products.query": {"type": "choice", "values": ["headphones", "Sony", "iPad"]},
                "add_to_cart.quantity": {"type": "int", "range": [1, 2]},
            },
        },
        "buy_and_review_8": {
            "description": "Search, details, add to cart, shipping, list addr+pay, place order, track, write review",
            "chain": ["search_products", "get_product_details", "add_to_cart", "select_shipping_option", "list_addresses", "list_payment_methods", "place_order", "write_review"],
            "param_flow": {
                "get_product_details.product_id": {"from_tool": "search_products", "field": "product_id", "index": 0},
                "add_to_cart.product_id": {"from_tool": "search_products", "field": "product_id", "index": 0},
                "add_to_cart.variant_id": {"from_tool": "get_product_details", "field": "variations[0].variant_id"},
                "add_to_cart.quantity": "user",
                "select_shipping_option.shipping_option": "user",
                "place_order.address_id": {"from_tool": "list_addresses", "field": "address_id", "index": 0},
                "place_order.payment_method_id": {"from_tool": "list_payment_methods", "field": "payment_method_id", "index": 0},
                "write_review.product_id": {"from_tool": "search_products", "field": "product_id", "index": 0},
                "write_review.rating": "user",
                "write_review.title": "user",
                "write_review.body": "user",
            },
            "user_params": {
                "search_products.query": {"type": "choice", "values": ["headphones", "Sony"]},
                "add_to_cart.quantity": {"type": "int", "range": [1, 2]},
                "select_shipping_option.shipping_option": {"type": "choice", "values": ["standard", "expedited", "prime_two_day"]},
                "write_review.rating": {"type": "int", "range": [3, 5]},
                "write_review.title": {"type": "choice", "values": ["Great product!", "Solid quality", "Good value"]},
                "write_review.body": {"type": "choice", "values": ["Works perfectly, very happy with my purchase.", "Exactly as described, fast shipping too."]},
            },
        },
    },

    # ================================================================
    # Booking.com — 4 to 5 step booking flow
    # ================================================================
    "booking": {
        "search_and_book_4": {
            "description": "Search properties, get room types, create booking, get booking",
            "chain": ["search_properties", "get_room_types", "create_booking", "get_booking"],
            "param_flow": {
                "get_room_types.property_id": {"from_tool": "search_properties", "field": "property_id", "index": 0},
                "get_room_types.check_in_date": "user",
                "get_room_types.check_out_date": "user",
                "create_booking.room_type_id": {"from_tool": "get_room_types", "field": "room_type_id", "index": 0},
                "create_booking.check_in_date": "user",
                "create_booking.check_out_date": "user",
                "create_booking.num_guests": "user",
                "get_booking.booking_id": {"from_tool": "create_booking", "field": "booking_id"},
            },
            "user_params": {
                "search_properties.city": {"type": "choice", "values": ["Paris", "Rome", "Tokyo", "New York", "London"]},
                "search_properties.check_in_date": {"type": "date"},
                "search_properties.check_out_date": {"type": "date"},
                "create_booking.num_guests": {"type": "int", "range": [1, 4]},
            },
        },
        "book_and_modify_5": {
            "description": "Search, get property details, room types, book, modify booking",
            "chain": ["search_properties", "get_property", "get_room_types", "create_booking", "modify_booking"],
            "param_flow": {
                "get_property.property_id": {"from_tool": "search_properties", "field": "property_id", "index": 0},
                "get_room_types.property_id": {"from_tool": "search_properties", "field": "property_id", "index": 0},
                "get_room_types.check_in_date": "user",
                "get_room_types.check_out_date": "user",
                "create_booking.room_type_id": {"from_tool": "get_room_types", "field": "room_type_id", "index": 0},
                "create_booking.check_in_date": "user",
                "create_booking.check_out_date": "user",
                "create_booking.num_guests": "user",
                "modify_booking.booking_id": {"from_tool": "create_booking", "field": "booking_id"},
                "modify_booking.num_guests": "user",
            },
            "user_params": {
                "search_properties.city": {"type": "choice", "values": ["Paris", "Rome", "Tokyo", "New York", "London"]},
                "search_properties.check_in_date": {"type": "date"},
                "search_properties.check_out_date": {"type": "date"},
                "create_booking.num_guests": {"type": "int", "range": [1, 3]},
                "modify_booking.num_guests": {"type": "int", "range": [2, 5]},
            },
        },
    },

    # ================================================================
    # Spotify — 4 to 5 step playlist creation
    # ================================================================
    "spotify": {
        "search_and_play_4": {
            "description": "Search tracks, get devices, transfer playback, play track",
            "chain": ["search_tracks", "get_devices", "transfer_playback", "play_track"],
            "param_flow": {
                "transfer_playback.device_id": {"from_tool": "get_devices", "field": "device_id", "index": 0},
                "play_track.track_id": {"from_tool": "search_tracks", "field": "song_id", "index": 0},
            },
            "user_params": {
                "search_tracks.query": {"type": "choice", "values": ["Velvet", "Midnight", "Horizon", "Burning", "Neon"]},
            },
        },
        "create_playlist_5": {
            "description": "Search artist, get top tracks, create playlist, add tracks, play playlist",
            "chain": ["search_artists", "get_artist_top_tracks", "create_playlist", "add_tracks_to_playlist", "play_context"],
            "param_flow": {
                "get_artist_top_tracks.artist_id": {"from_tool": "search_artists", "field": "artist_id", "index": 0},
                "add_tracks_to_playlist.playlist_id": {"from_tool": "create_playlist", "field": "$"},
                "add_tracks_to_playlist.track_ids": {"from_tool": "get_artist_top_tracks", "field": "song_id", "collect": True},
                "play_context.context_uri": {"from_tool": "create_playlist", "field": "$", "prefix": "playlist:"},
            },
            "user_params": {
                "search_artists.query": {"type": "choice", "values": ["Luna Prism", "DJ Korvus", "Phantom Relay", "Amara Sinclair"]},
                "create_playlist.name": {"type": "choice", "values": ["My Favorites", "Road Trip Mix", "Chill Vibes", "Workout Playlist"]},
            },
        },
    },

    # ================================================================
    # Instacart — 6 to 8 step grocery ordering
    # ================================================================
    "instacart": {
        "grocery_order_7": {
            "description": "Search stores, products, create cart, add to cart, delivery windows, list addresses, checkout",
            "chain": ["search_stores", "search_products", "create_cart", "add_to_cart", "get_delivery_windows", "list_addresses", "checkout"],
            "param_flow": {
                "search_products.store_id": {"from_tool": "search_stores", "field": "store_id", "index": 0},
                "create_cart.store_id": {"from_tool": "search_stores", "field": "store_id", "index": 0},
                "add_to_cart.cart_id": {"from_tool": "create_cart", "field": "$"},
                "add_to_cart.product_id": {"from_tool": "search_products", "field": "product_id", "index": 0},
                "add_to_cart.quantity": "user",
                "get_delivery_windows.store_id": {"from_tool": "search_stores", "field": "store_id", "index": 0},
                "checkout.cart_id": {"from_tool": "create_cart", "field": "$"},
                "checkout.address_id": {"from_tool": "list_addresses", "field": "address_id", "index": 0},
                "checkout.payment_method_id": {"from_tool": "list_payment_methods", "field": "payment_method_id", "index": 0, "implicit": True},
                "checkout.delivery_window_id": {"from_tool": "get_delivery_windows", "field": "window_id", "index": 0},
            },
            "user_params": {
                "search_stores.location": {"type": "literal", "value": {"lat": 37.7749, "lng": -122.4194}},
                "search_products.query": {"type": "choice", "values": ["milk", "bread", "eggs", "apples", "chicken"]},
                "add_to_cart.quantity": {"type": "int", "range": [3, 5]},
            },
        },
        "full_grocery_8": {
            "description": "Search stores, products, create cart, add items, get delivery windows, list addr+pay, checkout, get status",
            "chain": ["search_stores", "search_products", "create_cart", "add_to_cart", "get_delivery_windows", "list_addresses", "list_payment_methods", "checkout"],
            "param_flow": {
                "search_products.store_id": {"from_tool": "search_stores", "field": "store_id", "index": 0},
                "create_cart.store_id": {"from_tool": "search_stores", "field": "store_id", "index": 0},
                "add_to_cart.cart_id": {"from_tool": "create_cart", "field": "$"},
                "add_to_cart.product_id": {"from_tool": "search_products", "field": "product_id", "index": 0},
                "add_to_cart.quantity": "user",
                "get_delivery_windows.store_id": {"from_tool": "search_stores", "field": "store_id", "index": 0},
                "checkout.cart_id": {"from_tool": "create_cart", "field": "$"},
                "checkout.address_id": {"from_tool": "list_addresses", "field": "address_id", "index": 0},
                "checkout.payment_method_id": {"from_tool": "list_payment_methods", "field": "payment_method_id", "index": 0},
                "checkout.delivery_window_id": {"from_tool": "get_delivery_windows", "field": "window_id", "index": 0},
            },
            "user_params": {
                "search_stores.location": {"type": "literal", "value": {"lat": 37.7749, "lng": -122.4194}},
                "search_products.query": {"type": "choice", "values": ["milk", "bread", "eggs"]},
                "add_to_cart.quantity": {"type": "int", "range": [3, 5]},
            },
        },
    },

    # ================================================================
    # Google Calendar — 4 step event creation
    # ================================================================
    "google_calendar": {
        "create_event_4": {
            "description": "List calendars, create event, add attendee, set reminder",
            "chain": ["list_calendars", "create_event", "add_attendee", "set_event_reminder"],
            "param_flow": {
                "create_event.calendar_id": {"from_tool": "list_calendars", "field": "calendar_id", "index": 0},
                "create_event.title": "user",
                "create_event.start_time": "user",
                "create_event.end_time": "user",
                "add_attendee.event_id": {"from_tool": "create_event", "field": "event_id"},
                "add_attendee.email": "user",
                "set_event_reminder.event_id": {"from_tool": "create_event", "field": "event_id"},
                "set_event_reminder.reminders": "user",
            },
            "user_params": {
                "create_event.title": {"type": "choice", "values": ["Team standup", "Project review", "1:1 with manager", "Sprint planning"]},
                "create_event.start_time": {"type": "datetime"},
                "create_event.end_time": {"type": "datetime"},
                "add_attendee.email": {"type": "choice", "values": ["alice@company.com", "bob@company.com", "carol@company.com"]},
                "set_event_reminder.reminders": {"type": "literal", "value": [{"method": "popup", "minutes": 15}]},
            },
        },
        "create_and_move_5": {
            "description": "List calendars, create event, create new calendar, move event, get event",
            "chain": ["list_calendars", "create_event", "create_calendar", "move_event", "get_event"],
            "param_flow": {
                "create_event.calendar_id": {"from_tool": "list_calendars", "field": "calendar_id", "index": 0},
                "create_event.title": "user",
                "create_event.start_time": "user",
                "create_event.end_time": "user",
                "create_calendar.name": "user",
                "move_event.event_id": {"from_tool": "create_event", "field": "event_id"},
                "move_event.new_calendar_id": {"from_tool": "create_calendar", "field": "calendar_id"},
                "get_event.event_id": {"from_tool": "create_event", "field": "event_id"},
            },
            "user_params": {
                "create_event.title": {"type": "choice", "values": ["Team standup", "Project review", "Sprint planning"]},
                "create_event.start_time": {"type": "datetime"},
                "create_event.end_time": {"type": "datetime"},
                "create_calendar.name": {"type": "choice", "values": ["Side Projects", "Travel", "Reading List"]},
            },
        },
    },

    # ================================================================
    # Gmail — 4 to 5 step email workflow
    # ================================================================
    "gmail": {
        "draft_and_send_4": {
            "description": "List contacts, create draft, update draft, send draft",
            "chain": ["list_contacts", "create_draft", "update_draft", "send_draft"],
            "param_flow": {
                "create_draft.to": {"from_tool": "list_contacts", "field": "email_address", "index": 0, "wrap_list": True},
                "create_draft.subject": "user",
                "create_draft.body": "user",
                "update_draft.draft_id": {"from_tool": "create_draft", "field": "draft_id"},
                "update_draft.body": "user",
                "send_draft.draft_id": {"from_tool": "create_draft", "field": "draft_id"},
            },
            "user_params": {
                "create_draft.subject": {"type": "choice", "values": ["Meeting follow-up", "Project update", "Quick question"]},
                "create_draft.body": {"type": "choice", "values": ["Hi, just following up on our earlier conversation.", "Here's the latest project update."]},
                "update_draft.body": {"type": "choice", "values": ["Updated: Hi, just following up on our earlier conversation. Let me know if you have questions."]},
            },
        },
        "search_reply_forward_4": {
            "description": "Search emails, reply to email, forward email, get thread",
            "chain": ["search_emails", "reply_to_email", "forward_email", "get_thread"],
            "param_flow": {
                "search_emails.query": "user",
                "reply_to_email.email_id": {"from_tool": "search_emails", "field": "email_id", "index": 0},
                "reply_to_email.body": "user",
                "forward_email.email_id": {"from_tool": "search_emails", "field": "email_id", "index": 0},
                "forward_email.to": {"literal": ["brian.torres@gmail.com"]},
                "get_thread.thread_id": {"from_tool": "search_emails", "field": "thread_id", "index": 0},
            },
            "user_params": {
                "search_emails.query": {"type": "choice", "values": ["project", "meeting", "budget", "team"]},
                "reply_to_email.body": {"type": "choice", "values": ["Thanks for the update, I'll review and get back to you.", "Sounds good, let's proceed with that plan."]},
            },
        },
    },

    # ================================================================
    # Robinhood — 4 step trade flow
    # ================================================================
    "robinhood": {
        "search_and_trade_4": {
            "description": "Search stocks, get portfolio, place order, get order status",
            "chain": ["search_stocks", "get_portfolio", "place_order", "get_order"],
            "param_flow": {
                "place_order.symbol": {"from_tool": "search_stocks", "field": "symbol", "index": 0},
                "place_order.side": "user",
                "place_order.quantity": "user",
                "place_order.order_type": "user",
                "get_order.order_id": {"from_tool": "place_order", "field": "order_id"},
            },
            "user_params": {
                "search_stocks.query": {"type": "choice", "values": ["TSLA", "NVDA", "AMZN", "PLTR", "SOFI"]},
                "place_order.side": {"type": "choice", "values": ["buy", "sell"]},
                "place_order.quantity": {"type": "int", "range": [1, 10]},
                "place_order.order_type": {"type": "choice", "values": ["market", "limit"]},
            },
        },
    },

    # ================================================================
    # Uber — 4 to 5 step ride flow
    # ================================================================
    "uber": {
        "estimate_and_ride_4": {
            "description": "List ride types, estimate ride, request ride, get ride info",
            "chain": ["list_ride_types", "estimate_ride", "request_ride", "get_ride"],
            "param_flow": {
                "estimate_ride.ride_type_id": {"from_tool": "list_ride_types", "field": "name", "index": 0},
                "estimate_ride.pickup_lat": "user",
                "estimate_ride.pickup_lng": "user",
                "estimate_ride.dropoff_lat": "user",
                "estimate_ride.dropoff_lng": "user",
                "request_ride.ride_type_id": {"from_tool": "list_ride_types", "field": "name", "index": 0},
                "request_ride.pickup_lat": "user",
                "request_ride.pickup_lng": "user",
                "request_ride.dropoff_lat": "user",
                "request_ride.dropoff_lng": "user",
                "get_ride.ride_id": {"from_tool": "request_ride", "field": "ride_id"},
            },
            "user_params": {
                "estimate_ride.pickup_lat": {"type": "literal", "value": 37.7749},
                "estimate_ride.pickup_lng": {"type": "literal", "value": -122.4194},
                "estimate_ride.dropoff_lat": {"type": "literal", "value": 37.7899},
                "estimate_ride.dropoff_lng": {"type": "literal", "value": -122.4004},
                "request_ride.pickup_lat": {"type": "literal", "value": 37.7749},
                "request_ride.pickup_lng": {"type": "literal", "value": -122.4194},
                "request_ride.dropoff_lat": {"type": "literal", "value": 37.7899},
                "request_ride.dropoff_lng": {"type": "literal", "value": -122.4004},
            },
        },
        "ride_and_cancel_5": {
            "description": "List ride types, estimate, request ride, get ride status, cancel ride",
            "chain": ["list_ride_types", "estimate_ride", "request_ride", "get_ride", "cancel_ride"],
            "param_flow": {
                "estimate_ride.ride_type_id": {"from_tool": "list_ride_types", "field": "name", "index": 0},
                "estimate_ride.pickup_lat": "user",
                "estimate_ride.pickup_lng": "user",
                "estimate_ride.dropoff_lat": "user",
                "estimate_ride.dropoff_lng": "user",
                "request_ride.ride_type_id": {"from_tool": "list_ride_types", "field": "name", "index": 0},
                "request_ride.pickup_lat": "user",
                "request_ride.pickup_lng": "user",
                "request_ride.dropoff_lat": "user",
                "request_ride.dropoff_lng": "user",
                "get_ride.ride_id": {"from_tool": "request_ride", "field": "ride_id"},
                "cancel_ride.ride_id": {"from_tool": "request_ride", "field": "ride_id"},
            },
            "user_params": {
                "estimate_ride.pickup_lat": {"type": "literal", "value": 37.7749},
                "estimate_ride.pickup_lng": {"type": "literal", "value": -122.4194},
                "estimate_ride.dropoff_lat": {"type": "literal", "value": 37.7899},
                "estimate_ride.dropoff_lng": {"type": "literal", "value": -122.4004},
                "request_ride.pickup_lat": {"type": "literal", "value": 37.7749},
                "request_ride.pickup_lng": {"type": "literal", "value": -122.4194},
                "request_ride.dropoff_lat": {"type": "literal", "value": 37.7899},
                "request_ride.dropoff_lng": {"type": "literal", "value": -122.4004},
            },
        },
    },

    # ================================================================
    # Lyft — 4 to 5 step ride flow
    # ================================================================
    "lyft": {
        "estimate_and_ride_4": {
            "description": "List ride types, get estimates, request ride, get ride info",
            "chain": ["list_ride_types", "get_ride_estimates", "request_ride", "get_ride"],
            "param_flow": {
                "get_ride_estimates.pickup_lat": "user",
                "get_ride_estimates.pickup_lng": "user",
                "get_ride_estimates.dropoff_lat": "user",
                "get_ride_estimates.dropoff_lng": "user",
                "request_ride.ride_type_id": {"from_tool": "list_ride_types", "field": "name", "index": 0},
                "request_ride.pickup_lat": "user",
                "request_ride.pickup_lng": "user",
                "request_ride.dropoff_lat": "user",
                "request_ride.dropoff_lng": "user",
                "get_ride.ride_id": {"from_tool": "request_ride", "field": "ride_id"},
            },
            "user_params": {
                "get_ride_estimates.pickup_lat": {"type": "literal", "value": 34.0522},
                "get_ride_estimates.pickup_lng": {"type": "literal", "value": -118.2437},
                "get_ride_estimates.dropoff_lat": {"type": "literal", "value": 34.0195},
                "get_ride_estimates.dropoff_lng": {"type": "literal", "value": -118.4912},
                "request_ride.pickup_lat": {"type": "literal", "value": 34.0522},
                "request_ride.pickup_lng": {"type": "literal", "value": -118.2437},
                "request_ride.dropoff_lat": {"type": "literal", "value": 34.0195},
                "request_ride.dropoff_lng": {"type": "literal", "value": -118.4912},
            },
        },
        "ride_and_cancel_5": {
            "description": "List ride types, estimates, request ride, get ride status, cancel ride",
            "chain": ["list_ride_types", "get_ride_estimates", "request_ride", "get_ride", "cancel_ride"],
            "param_flow": {
                "get_ride_estimates.pickup_lat": "user",
                "get_ride_estimates.pickup_lng": "user",
                "get_ride_estimates.dropoff_lat": "user",
                "get_ride_estimates.dropoff_lng": "user",
                "request_ride.ride_type_id": {"from_tool": "list_ride_types", "field": "name", "index": 0},
                "request_ride.pickup_lat": "user",
                "request_ride.pickup_lng": "user",
                "request_ride.dropoff_lat": "user",
                "request_ride.dropoff_lng": "user",
                "get_ride.ride_id": {"from_tool": "request_ride", "field": "ride_id"},
                "cancel_ride.ride_id": {"from_tool": "request_ride", "field": "ride_id"},
            },
            "user_params": {
                "get_ride_estimates.pickup_lat": {"type": "literal", "value": 34.0522},
                "get_ride_estimates.pickup_lng": {"type": "literal", "value": -118.2437},
                "get_ride_estimates.dropoff_lat": {"type": "literal", "value": 34.0195},
                "get_ride_estimates.dropoff_lng": {"type": "literal", "value": -118.4912},
                "request_ride.pickup_lat": {"type": "literal", "value": 34.0522},
                "request_ride.pickup_lng": {"type": "literal", "value": -118.2437},
                "request_ride.dropoff_lat": {"type": "literal", "value": 34.0195},
                "request_ride.dropoff_lng": {"type": "literal", "value": -118.4912},
            },
        },
    },

    # ================================================================
    # === ADDITIONAL 6-8 STEP TEMPLATES ===
    # (Merged into existing server keys via _EXTRA_TEMPLATES below)
    # ================================================================
}

_EXTRA_TEMPLATES = {
    "spotify": {
        "playlist_and_queue_6": {
            "description": "Search tracks, get devices, transfer playback, create playlist, add tracks, play playlist",
            "chain": ["search_tracks", "get_devices", "transfer_playback", "create_playlist", "add_tracks_to_playlist", "play_context"],
            "param_flow": {
                "transfer_playback.device_id": {"from_tool": "get_devices", "field": "device_id", "index": 0},
                "add_tracks_to_playlist.playlist_id": {"from_tool": "create_playlist", "field": "$"},
                "add_tracks_to_playlist.track_ids": {"from_tool": "search_tracks", "field": "song_id", "collect": True},
                "play_context.context_uri": {"from_tool": "create_playlist", "field": "$", "prefix": "playlist:"},
            },
            "user_params": {
                "search_tracks.query": {"type": "choice", "values": ["Velvet", "Midnight", "Horizon", "Burning", "Neon"]},
                "create_playlist.name": {"type": "choice", "values": ["My Mix", "Evening Vibes", "Focus Music"]},
            },
        },
        "artist_deep_dive_7": {
            "description": "Search artist, get top tracks, get artist info, create playlist, add tracks, update playlist details, play",
            "chain": ["search_artists", "get_artist_top_tracks", "get_artist", "create_playlist", "add_tracks_to_playlist", "update_playlist_details", "play_context"],
            "param_flow": {
                "get_artist_top_tracks.artist_id": {"from_tool": "search_artists", "field": "artist_id", "index": 0},
                "get_artist.artist_id": {"from_tool": "search_artists", "field": "artist_id", "index": 0},
                "add_tracks_to_playlist.playlist_id": {"from_tool": "create_playlist", "field": "$"},
                "add_tracks_to_playlist.track_ids": {"from_tool": "get_artist_top_tracks", "field": "song_id", "collect": True},
                "update_playlist_details.playlist_id": {"from_tool": "create_playlist", "field": "$"},
                "update_playlist_details.description": "user",
                "play_context.context_uri": {"from_tool": "create_playlist", "field": "$", "prefix": "playlist:"},
            },
            "user_params": {
                "search_artists.query": {"type": "choice", "values": ["Luna Prism", "DJ Korvus", "Phantom Relay", "Amara Sinclair"]},
                "create_playlist.name": {"type": "choice", "values": ["Best Of", "Top Hits", "Artist Collection"]},
                "update_playlist_details.description": {"type": "choice", "values": ["A collection of the best tracks", "My favorite songs from this artist"]},
            },
        },
        "discover_and_save_8": {
            "description": "Search artist, get top tracks, get recommendations, save tracks, create playlist, add tracks, get playlist, play",
            "chain": ["search_artists", "get_artist_top_tracks", "get_recommendations", "save_tracks", "create_playlist", "add_tracks_to_playlist", "get_playlist", "play_context"],
            "param_flow": {
                "get_artist_top_tracks.artist_id": {"from_tool": "search_artists", "field": "artist_id", "index": 0},
                "get_recommendations.seed_tracks": {"from_tool": "get_artist_top_tracks", "field": "song_id", "collect": True},
                "save_tracks.track_ids": {"from_tool": "get_artist_top_tracks", "field": "song_id", "collect": True},
                "add_tracks_to_playlist.playlist_id": {"from_tool": "create_playlist", "field": "$"},
                "add_tracks_to_playlist.track_ids": {"from_tool": "get_artist_top_tracks", "field": "song_id", "collect": True},
                "get_playlist.playlist_id": {"from_tool": "create_playlist", "field": "$"},
                "play_context.context_uri": {"from_tool": "create_playlist", "field": "$", "prefix": "playlist:"},
            },
            "user_params": {
                "search_artists.query": {"type": "choice", "values": ["Luna Prism", "DJ Korvus", "Phantom Relay", "Amara Sinclair"]},
                "create_playlist.name": {"type": "choice", "values": ["Discovery Mix", "New Finds", "Fresh Tracks"]},
            },
        },
    },

    # ── Booking long chains ──
    "booking": {
        "book_and_cancel_6": {
            "description": "Search properties, get property details, get room types, create booking, get booking, cancel booking",
            "chain": ["search_properties", "get_property", "get_room_types", "create_booking", "get_booking", "cancel_booking"],
            "param_flow": {
                "get_property.property_id": {"from_tool": "search_properties", "field": "property_id", "index": 0},
                "get_room_types.property_id": {"from_tool": "search_properties", "field": "property_id", "index": 0},
                "get_room_types.check_in_date": "user",
                "get_room_types.check_out_date": "user",
                "create_booking.room_type_id": {"from_tool": "get_room_types", "field": "room_type_id", "index": 0},
                "create_booking.check_in_date": "user",
                "create_booking.check_out_date": "user",
                "create_booking.num_guests": "user",
                "get_booking.booking_id": {"from_tool": "create_booking", "field": "booking_id"},
                "cancel_booking.booking_id": {"from_tool": "create_booking", "field": "booking_id"},
            },
            "user_params": {
                "search_properties.city": {"type": "choice", "values": ["Paris", "Rome", "Tokyo", "New York", "London"]},
                "search_properties.check_in_date": {"type": "date"},
                "search_properties.check_out_date": {"type": "date"},
                "create_booking.num_guests": {"type": "int", "range": [1, 3]},
            },
        },
    },

    "gmail": {
        "compose_and_organize_6": {
            "description": "List contacts, send email, search emails, star email, add label, get thread",
            "chain": ["list_contacts", "send_email", "search_emails", "star_email", "add_label", "get_thread"],
            "param_flow": {
                "send_email.to": {"from_tool": "list_contacts", "field": "email_address", "index": 0, "wrap_list": True},
                "send_email.subject": "user",
                "send_email.body": "user",
                "search_emails.query": "user",
                "star_email.email_id": {"from_tool": "search_emails", "field": "email_id", "index": 0},
                "add_label.email_id": {"from_tool": "search_emails", "field": "email_id", "index": 0},
                "add_label.label": "user",
                "get_thread.thread_id": {"from_tool": "search_emails", "field": "thread_id", "index": 0},
            },
            "user_params": {
                "send_email.subject": {"type": "choice", "values": ["Quick update", "Follow-up", "Status report"]},
                "send_email.body": {"type": "choice", "values": ["Just wanted to share a quick update on the project.", "Following up on our earlier conversation."]},
                "search_emails.query": {"type": "choice", "values": ["project", "budget", "team"]},
                "add_label.label": {"type": "choice", "values": ["important", "follow-up", "urgent"]},
            },
        },
        "full_draft_workflow_8": {
            "description": "List contacts, create draft, update draft, send draft, search emails, reply, star, get thread",
            "chain": ["list_contacts", "create_draft", "update_draft", "send_draft", "search_emails", "reply_to_email", "star_email", "get_thread"],
            "param_flow": {
                "create_draft.to": {"from_tool": "list_contacts", "field": "email_address", "index": 0, "wrap_list": True},
                "create_draft.subject": "user",
                "create_draft.body": "user",
                "update_draft.draft_id": {"from_tool": "create_draft", "field": "draft_id"},
                "update_draft.body": "user",
                "send_draft.draft_id": {"from_tool": "create_draft", "field": "draft_id"},
                "search_emails.query": "user",
                "reply_to_email.email_id": {"from_tool": "search_emails", "field": "email_id", "index": 0},
                "reply_to_email.body": "user",
                "star_email.email_id": {"from_tool": "search_emails", "field": "email_id", "index": 0},
                "get_thread.thread_id": {"from_tool": "search_emails", "field": "thread_id", "index": 0},
            },
            "user_params": {
                "create_draft.subject": {"type": "choice", "values": ["Project update", "Meeting notes"]},
                "create_draft.body": {"type": "choice", "values": ["Here is the latest update.", "Notes from today's meeting."]},
                "update_draft.body": {"type": "choice", "values": ["Updated: Here is the latest update with revisions.", "Revised: Notes from today's meeting with action items."]},
                "search_emails.query": {"type": "choice", "values": ["project", "budget", "team"]},
                "reply_to_email.body": {"type": "choice", "values": ["Thanks, I'll take a look.", "Got it, will follow up."]},
            },
        },
    },

    "google_calendar": {
        "full_event_management_6": {
            "description": "List calendars, create event, add attendee, set reminder, update event, get event",
            "chain": ["list_calendars", "create_event", "add_attendee", "set_event_reminder", "update_event", "get_event"],
            "param_flow": {
                "create_event.calendar_id": {"from_tool": "list_calendars", "field": "calendar_id", "index": 0},
                "create_event.title": "user",
                "create_event.start_time": "user",
                "create_event.end_time": "user",
                "add_attendee.event_id": {"from_tool": "create_event", "field": "event_id"},
                "add_attendee.email": "user",
                "set_event_reminder.event_id": {"from_tool": "create_event", "field": "event_id"},
                "update_event.event_id": {"from_tool": "create_event", "field": "event_id"},
                "update_event.location": "user",
                "get_event.event_id": {"from_tool": "create_event", "field": "event_id"},
            },
            "user_params": {
                "create_event.title": {"type": "choice", "values": ["Team standup", "Sprint planning", "Design review"]},
                "create_event.start_time": {"type": "datetime"},
                "create_event.end_time": {"type": "datetime"},
                "add_attendee.email": {"type": "choice", "values": ["alice@company.com", "bob@company.com"]},
                "update_event.location": {"type": "choice", "values": ["Conference Room A", "Zoom Meeting", "Building 2 Room 301"]},
            },
        },
        "create_move_and_update_7": {
            "description": "List calendars, create calendar, create event, add attendee, move event, set reminder, get event",
            "chain": ["list_calendars", "create_calendar", "create_event", "add_attendee", "move_event", "set_event_reminder", "get_event"],
            "param_flow": {
                "create_event.calendar_id": {"from_tool": "list_calendars", "field": "calendar_id", "index": 0},
                "create_event.title": "user",
                "create_event.start_time": "user",
                "create_event.end_time": "user",
                "create_calendar.name": "user",
                "add_attendee.event_id": {"from_tool": "create_event", "field": "event_id"},
                "add_attendee.email": "user",
                "move_event.event_id": {"from_tool": "create_event", "field": "event_id"},
                "move_event.new_calendar_id": {"from_tool": "create_calendar", "field": "calendar_id"},
                "set_event_reminder.event_id": {"from_tool": "create_event", "field": "event_id"},
                "get_event.event_id": {"from_tool": "create_event", "field": "event_id"},
            },
            "user_params": {
                "create_event.title": {"type": "choice", "values": ["Sprint planning", "1:1 with manager", "Team retrospective"]},
                "create_event.start_time": {"type": "datetime"},
                "create_event.end_time": {"type": "datetime"},
                "create_calendar.name": {"type": "choice", "values": ["Side Projects", "Travel", "Reading List"]},
                "add_attendee.email": {"type": "choice", "values": ["alice@company.com", "bob@company.com", "carol@company.com"]},
            },
        },
    },

    "robinhood": {
        "trade_and_watchlist_6": {
            "description": "Search stocks, get portfolio, place order, get order, get watchlist, get dividends",
            "chain": ["search_stocks", "get_portfolio", "place_order", "get_order", "get_watchlist", "get_dividends"],
            "param_flow": {
                "place_order.symbol": {"from_tool": "search_stocks", "field": "symbol", "index": 0},
                "place_order.side": "user",
                "place_order.quantity": "user",
                "place_order.order_type": "user",
                "get_order.order_id": {"from_tool": "place_order", "field": "order_id"},
            },
            "user_params": {
                "search_stocks.query": {"type": "choice", "values": ["TSLA", "NVDA", "AMZN", "PLTR", "SOFI"]},
                "place_order.side": {"type": "choice", "values": ["buy", "sell"]},
                "place_order.quantity": {"type": "int", "range": [1, 10]},
                "place_order.order_type": {"type": "choice", "values": ["market", "limit"]},
            },
        },
        "full_trade_flow_7": {
            "description": "Search stocks, get portfolio, get account, place order, get order, list orders, get portfolio history",
            "chain": ["search_stocks", "get_portfolio", "get_account", "place_order", "get_order", "list_orders", "get_portfolio_history"],
            "param_flow": {
                "place_order.symbol": {"from_tool": "search_stocks", "field": "symbol", "index": 0},
                "place_order.side": "user",
                "place_order.quantity": "user",
                "place_order.order_type": "user",
                "get_order.order_id": {"from_tool": "place_order", "field": "order_id"},
            },
            "user_params": {
                "search_stocks.query": {"type": "choice", "values": ["TSLA", "NVDA", "AMZN", "PLTR", "SOFI"]},
                "place_order.side": {"type": "choice", "values": ["buy", "sell"]},
                "place_order.quantity": {"type": "int", "range": [1, 5]},
                "place_order.order_type": {"type": "choice", "values": ["market", "limit"]},
            },
        },
    },

    "uber_eats": {
        "full_order_7": {
            "description": "Search restaurants, get restaurant details, get menu, get profile, get offers, place order, track order",
            "chain": ["search_restaurants", "get_restaurant", "get_menu", "get_profile", "get_available_offers", "place_order", "track_order"],
            "param_flow": {
                "get_restaurant.restaurant_id": {"from_tool": "search_restaurants", "field": "restaurant_id", "index": 0},
                "get_menu.restaurant_id": {"from_tool": "search_restaurants", "field": "restaurant_id", "index": 0},
                "place_order.restaurant_id": {"from_tool": "search_restaurants", "field": "restaurant_id", "index": 0},
                "place_order.items": {"composite": "order_items", "item_id_from": {"from_tool": "get_menu", "field": "item_id", "index": 0}, "quantity_from": "user"},
                "place_order.delivery_address_id": {"from_tool": "get_profile", "field": "address[0].address_id"},
                "place_order.payment_method_id": {"from_tool": "get_profile", "field": "payment_method[0].method_id"},
                "place_order.offer_id": {"from_tool": "get_available_offers", "field": "offer_id", "index": 0},
                "track_order.order_id": {"from_tool": "place_order", "field": "$"},
            },
            "user_params": {
                "search_restaurants.category": {"type": "choice", "values": ["Thai", "Mexican", "Indian", "Chinese", "Japanese", "Italian"]},
                "place_order.items.quantity": {"type": "int", "range": [2, 3]},
            },
        },
        "order_history_and_track_8": {
            "description": "Search restaurants, get menu, get profile, get offers, place order, get order, get order history, track order",
            "chain": ["search_restaurants", "get_menu", "get_profile", "get_available_offers", "place_order", "get_order", "get_order_history", "track_order"],
            "param_flow": {
                "get_menu.restaurant_id": {"from_tool": "search_restaurants", "field": "restaurant_id", "index": 0},
                "place_order.restaurant_id": {"from_tool": "search_restaurants", "field": "restaurant_id", "index": 0},
                "place_order.items": {"composite": "order_items", "item_id_from": {"from_tool": "get_menu", "field": "item_id", "index": 0}, "quantity_from": "user"},
                "place_order.delivery_address_id": {"from_tool": "get_profile", "field": "address[0].address_id"},
                "place_order.payment_method_id": {"from_tool": "get_profile", "field": "payment_method[0].method_id"},
                "place_order.offer_id": {"from_tool": "get_available_offers", "field": "offer_id", "index": 0},
                "get_order.order_id": {"from_tool": "place_order", "field": "$"},
                "track_order.order_id": {"from_tool": "place_order", "field": "$"},
            },
            "user_params": {
                "search_restaurants.category": {"type": "choice", "values": ["Thai", "Mexican", "Indian", "Chinese"]},
                "place_order.items.quantity": {"type": "int", "range": [2, 3]},
            },
        },
    },
}


def _merged_templates() -> dict:
    """Merge CHAIN_TEMPLATES and _EXTRA_TEMPLATES."""
    merged = {}
    for d in (CHAIN_TEMPLATES, _EXTRA_TEMPLATES):
        for server, templates in d.items():
            merged.setdefault(server, {}).update(templates)
    return merged


def get_all_templates() -> dict:
    """Return all chain templates, flat: {server_name/template_name: template}."""
    flat = {}
    for server, templates in _merged_templates().items():
        for tname, tdef in templates.items():
            flat[f"{server}/{tname}"] = {**tdef, "server": server}
    return flat


def get_templates_by_length(min_len: int = 4, max_len: int = 8) -> dict:
    """Return templates filtered by chain length."""
    return {
        k: v for k, v in get_all_templates().items()
        if min_len <= len(v["chain"]) <= max_len
    }
