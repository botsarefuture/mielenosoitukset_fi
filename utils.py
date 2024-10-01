CITY_LIST = ['Akaa', 'Alajärvi', 'Alavieska', 'Alavus', 'Asikkala', 'Askola', 'Aura', 'Brändö', 'Eckerö', 'Enonkoski', 'Enontekiö', 'Espoo', 'Eura', 'Eurajoki', 'Evijärvi', 'Finström', 'Forssa', 'Föglö', 'Geta', 'Haapajärvi', 'Haapavesi', 'Hailuoto', 'Halsua', 'Hamina', 'Hammarland', 'Hankasalmi', 'Hanko', 'Harjavalta', 'Hartola', 'Hattula', 'Hausjärvi', 'Heinola', 'Heinävesi', 'Helsinki', 'Hirvensalmi', 'Hollola', 'Huittinen', 'Humppila', 'Hyrynsalmi', 'Hyvinkää', 'Hämeenkyrö', 'Hämeenlinna', 'Ii', 'Iisalmi', 'Iitti', 'Ikaalinen', 'Ilmajoki', 'Ilomantsi', 'Imatra', 'Inari', 'Inkoo', 'Isojoki', 'Isokyrö', 'Janakkala', 'Joensuu', 'Jokioinen', 'Jomala', 'Joroinen', 'Joutsa', 'Juuka', 'Juupajoki', 'Juva', 'Jyväskylä', 'Jämijärvi', 'Jämsä', 'Järvenpää', 'Kaarina', 'Kaavi', 'Kajaani', 'Kalajoki', 'Kangasala', 'Kangasniemi', 'Kankaanpää', 'Kannonkoski', 'Kannus', 'Karijoki', 'Karkkila', 'Karstula', 'Karvia', 'Kaskinen', 'Kauhajoki', 'Kauhava', 'Kauniainen', 'Kaustinen', 'Keitele', 'Kemi', 'Kemijärvi', 'Keminmaa', 'Kemiönsaari', 'Kempele', 'Kerava', 'Keuruu', 'Kihniö', 'Kinnula', 'Kirkkonummi', 'Kitee', 'Kittilä', 'Kiuruvesi', 'Kivijärvi', 'Kokemäki', 'Kokkola', 'Kolari', 'Konnevesi', 'Kontiolahti', 'Korsnäs', 'Koski Tl', 'Kotka', 'Kouvola', 'Kristiinankaupunki', 'Kruunupyy', 'Kuhmo', 'Kuhmoinen', 'Kumlinge', 'Kuopio', 'Kuortane', 'Kurikka', 'Kustavi', 'Kuusamo', 'Kyyjärvi', 'Kärkölä', 'Kärsämäki', 'Kökar', 'Lahti', 'Laihia', 'Laitila', 'Lapinjärvi', 'Lapinlahti', 'Lappajärvi', 'Lappeenranta', 'Lapua', 'Laukaa', 'Lemi', 'Lemland', 'Lempäälä', 'Leppävirta', 'Lestijärvi', 'Lieksa', 'Lieto', 'Liminka', 'Liperi', 'Lohja', 'Loimaa', 'Loppi', 'Loviisa', 'Luhanka', 'Lumijoki', 'Lumparland', 'Luoto', 'Luumäki', 'Maalahti', 'Maarianhamina – Mariehamn', 'Marttila', 'Masku', 'Merijärvi', 'Merikarvia', 'Miehikkälä', 'Mikkeli', 'Muhos', 'Multia', 'Muonio', 'Mustasaari', 'Muurame', 'Mynämäki', 'Myrskylä', 'Mäntsälä', 'Mänttä-Vilppula', 'Mäntyharju', 'Naantali', 'Nakkila', 'Nivala', 'Nokia', 'Nousiainen', 'Nurmes', 'Nurmijärvi', 'Närpiö', 'Orimattila', 'Oripää', 'Orivesi', 'Oulainen', 'Oulu', 'Outokumpu', 'Padasjoki', 'Paimio', 'Paltamo', 'Parainen', 'Parikkala', 'Parkano', 'Pedersöre', 'Pelkosenniemi', 'Pello', 'Perho', 'Pertunmaa', 'Petäjävesi', 'Pieksämäki', 'Pielavesi', 'Pietarsaari', 'Pihtipudas', 'Pirkkala', 'Polvijärvi', 'Pomarkku', 'Pori', 'Pornainen', 'Porvoo', 'Posio', 'Pudasjärvi', 'Pukkila', 'Punkalaidun', 'Puolanka', 'Puumala', 'Pyhtää', 'Pyhäjoki', 'Pyhäjärvi', 'Pyhäntä', 'Pyhäranta', 'Pälkäne', 'Pöytyä', 'Raahe', 'Raasepori', 'Raisio', 'Rantasalmi', 'Ranua', 'Rauma', 'Rautalampi', 'Rautavaara', 'Rautjärvi', 'Reisjärvi', 'Riihimäki', 'Ristijärvi', 'Rovaniemi', 'Ruokolahti', 'Ruovesi', 'Rusko', 'Rääkkylä', 'Saarijärvi', 'Salla', 'Salo', 'Saltvik', 'Sastamala', 'Sauvo', 'Savitaipale', 'Savonlinna', 'Savukoski', 'Seinäjoki', 'Sievi', 'Siikainen', 'Siikajoki', 'Siikalatva', 'Siilinjärvi', 'Simo', 'Sipoo', 'Siuntio', 'Sodankylä', 'Soini', 'Somero', 'Sonkajärvi', 'Sotkamo', 'Sottunga', 'Sulkava', 'Sund', 'Suomussalmi', 'Suonenjoki', 'Sysmä', 'Säkylä', 'Taipalsaari', 'Taivalkoski', 'Taivassalo', 'Tammela', 'Tampere', 'Tervo', 'Tervola', 'Teuva', 'Tohmajärvi', 'Toholampi', 'Toivakka', 'Tornio', 'Turku', 'Tuusniemi', 'Tuusula', 'Tyrnävä', 'Ulvila', 'Urjala', 'Utajärvi', 'Utsjoki', 'Uurainen', 'Uusikaarlepyy', 'Uusikaupunki', 'Vaala', 'Vaasa', 'Valkeakoski', 'Vantaa', 'Varkaus', 'Vehmaa', 'Vesanto', 'Vesilahti', 'Veteli', 'Vieremä', 'Vihti', 'Viitasaari', 'Vimpeli', 'Virolahti', 'Virrat', 'Vårdö', 'Vöyri', 'Ylitornio', 'Ylivieska', 'Ylöjärvi', 'Ypäjä', 'Ähtäri', 'Äänekoski']

PERMISSIONS_GROUPS = {
    'Demo Management': [
        {'name': 'EDIT_DEMO', 'description': 'Allows the user to edit demo content.'},
        {'name': 'CREATE_DEMO', 'description': 'Allows the user to create demo content.'},
        {'name': 'DELETE_DEMO', 'description': 'Allows the user to delete demo content.'},
        {'name': 'VIEW_DEMO', 'description': 'Allows the user to view demo details.'},
        {'name': 'MANAGE_DEMO_PARTICIPANTS', 'description': 'Allows the user to manage participants in a demonstration.'},
        {'name': 'NOTIFY_PARTICIPANTS', 'description': 'Allows the user to send notifications to participants.'},
    ],
    'Event Management': [
        {'name': 'CREATE_EVENT', 'description': 'Allows the user to create new events related to demonstrations.'},
        {'name': 'EDIT_EVENT', 'description': 'Allows the user to edit existing events.'},
        {'name': 'DELETE_EVENT', 'description': 'Allows the user to delete events.'},
        {'name': 'VIEW_EVENT', 'description': 'Allows the user to view event details.'},
    ],
    'Organization Management': [
        {'name': 'MANAGE_ORGANIZATIONS', 'description': 'Allows the user to manage organizations related to demonstrations.'},
        {'name': 'EDIT_ORGANIZATION', 'description': 'Allows the user to edit organization details.'},
        {'name': 'VIEW_ORGANIZATION', 'description': 'Allows the user to view organization details.'},
    ],
    'Media Management': [
        {'name': 'CREATE_MEDIA', 'description': 'Allows the user to upload media (images, videos) related to demonstrations.'},
        {'name': 'DELETE_MEDIA', 'description': 'Allows the user to delete uploaded media.'},
        {'name': 'VIEW_MEDIA', 'description': 'Allows the user to view uploaded media.'},
    ],
    'Feedback and Reporting': [
        {'name': 'MANAGE_FEEDBACK', 'description': 'Allows the user to manage feedback from participants.'},
        {'name': 'VIEW_REPORTS', 'description': 'Allows the user to view reports on demonstrations.'},
    ],
    'Admin Management': [
        {'name': 'MANAGE_ADMIN_USERS', 'description': 'Allows the user to manage other admin users.'},
        {'name': 'VIEW_USER_DATA', 'description': 'Allows the user to view data of other users.'},
        {'name': 'EDIT_USER_DATA', 'description': 'Allows the user to edit data of other users.'},
        {'name': 'DELETE_USER', 'description': 'Allows the user to delete other users.'},
    ],
    'Petition Management': [
        {'name': 'CREATE_PETITION', 'description': 'Allows the user to create a petition related to a demonstration.'},
        {'name': 'SIGN_PETITION', 'description': 'Allows the user to sign petitions.'},
        {'name': 'VIEW_PETITION', 'description': 'Allows the user to view petitions.'},
        {'name': 'NOTIFY_PETITION_SIGNERS', 'description': 'Allows the user to notify petition signers.'},
    ],
}
