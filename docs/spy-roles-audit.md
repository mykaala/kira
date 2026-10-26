# Out of Place: role audit

One judge call per distinct role title (334 titles for 400 roles; model gpt-5.6-luna, $0.074). The judge saw only the title and the 40-place list, and listed every place where a person with that title plausibly works or would be found. The audit calls a role generic when it fits >= 5 places. Nothing in the bank was changed.

## How many places each role fits

| Places | Roles |
|---|---|
| 0 | 13 |
| 1 | 148 |
| 2 | 51 |
| 3 | 24 |
| 4 | 27 |
| 5 | 12 |
| 6 | 9 |
| 7 | 6 |
| 8 | 4 |
| 9 | 3 |
| 10 | 2 |
| 11 | 8 |
| 12 | 6 |
| 13 | 2 |
| 14 | 2 |
| 15 | 3 |
| 16 | 1 |
| 17 | 1 |
| 18 | 8 |
| 19 | 11 |
| 20 | 1 |
| 21 | 1 |
| 22 | 1 |
| 23 | 1 |
| 24 | 18 |
| 25 | 1 |
| 27 | 1 |
| 29 | 2 |
| 31 | 1 |
| 32 | 1 |
| 33 | 1 |
| 35 | 2 |
| 36 | 7 |
| 37 | 20 |
| 40 | 1 |

Mean 7.8; generic-flagged roles mean 16.7, the rest 2.0.

## Roles that fit only one place (148)

| Place | Title | Fits | Places it fits |
|---|---|---|---|
| airport lounge | night traveler | 1 | overnight bus |
| airport lounge | access host | 1 | airport lounge |
| airport lounge | rebooking specialist | 1 | airport lounge |
| airport lounge | nap-pod guest | 1 | airport lounge |
| aquarium | tank diver | 1 | aquarium |
| aquarium | jellyfish keeper | 1 | aquarium |
| aquarium | ray feeder | 1 | aquarium |
| aquarium | coral grower | 1 | aquarium |
| botanical garden | orchid keeper | 1 | botanical garden |
| botanical garden | rose pruner | 1 | botanical garden |
| botanical garden | plant labeler | 1 | botanical garden |
| botanical garden | irrigation technician | 1 | botanical garden |
| botanical garden | greenhouse grower | 1 | botanical garden |
| bowling alley | pinsetter technician | 1 | bowling alley |
| bowling alley | shoe counter clerk | 1 | bowling alley |
| bowling alley | ball fitter | 1 | bowling alley |
| butterfly house | wing keeper | 1 | butterfly house |
| butterfly house | nectar mixer | 1 | butterfly house |
| butterfly house | pupa caretaker | 1 | butterfly house |
| butterfly house | plant tender | 1 | botanical garden |
| cable car | cabin attendant | 1 | ferry |
| cable car | window photographer | 1 | photo studio |
| car wash | tunnel attendant | 1 | aquarium |
| car wash | detailer | 1 | car wash |
| car wash | vacuum bay worker | 1 | car wash |
| cinema | projectionist | 1 | cinema |
| cinema | 3d glasses clerk | 1 | cinema |
| cinema | matinee regular | 1 | cinema |
| county fair | livestock exhibitor | 1 | county fair |
| county fair | ribbon judge | 1 | county fair |
| county fair | tractor pull driver | 1 | county fair |
| county fair | ride mechanic | 1 | county fair |
| county fair | pie contestant | 1 | county fair |
| dentist office | dental hygienist | 1 | dentist office |
| dentist office | chairside assistant | 1 | dentist office |
| dentist office | x-ray technician | 1 | dentist office |
| dentist office | braces specialist | 1 | dentist office |
| dentist office | anxious patient | 1 | dentist office |
| ferry | deckhand | 1 | ferry |
| ferry | wheelhouse officer | 1 | ferry |
| ferry | galley cook | 1 | ferry |
| ferry | rope handler | 1 | ferry |
| food truck rally | order caller | 1 | food truck rally |
| food truck rally | fryer cook | 1 | food truck rally |
| food truck rally | sauce runner | 1 | food truck rally |
| food truck rally | propane checker | 1 | hardware store |
| hair salon | colorist | 1 | hair salon |
| hair salon | shampoo assistant | 1 | hair salon |
| hair salon | apprentice | 1 | hair salon |
| hair salon | extension specialist | 1 | lecture hall |
| hair salon | blowout specialist | 1 | hair salon |
| hair salon | shop manager | 1 | hardware store |
| hardware store | paint mixer | 1 | hardware store |
| hardware store | key cutter | 1 | hardware store |
| hardware store | lumber loader | 1 | hardware store |
| hardware store | tool demonstrator | 1 | hardware store |
| hardware store | fastener specialist | 1 | hardware store |
| hardware store | weekend fixer | 1 | hardware store |
| hardware store | stock receiver | 1 | hardware store |
| hardware store | regular contractor | 1 | hardware store |
| hardware store | garden advisor | 1 | botanical garden |
| hot spring | mineral guide | 1 | nature reserve |
| hot spring | mud wrapper | 1 | hot spring |
| ice fishing camp | hole driller | 1 | ice fishing camp |
| ice fishing camp | tip-up watcher | 1 | ice fishing camp |
| ice fishing camp | minnow keeper | 1 | aquarium |
| ice fishing camp | shack hauler | 1 | ice fishing camp |
| ice fishing camp | catch cook | 1 | ice fishing camp |
| ice fishing camp | lake guide | 1 | ice fishing camp |
| ice rink | hockey goalie | 1 | ice rink |
| ice rink | figure skater | 1 | ice rink |
| ice rink | resurfacer driver | 1 | ice rink |
| ice rink | hockey referee | 1 | ice rink |
| karaoke bar | lyric screen operator | 1 | karaoke bar |
| karaoke bar | duet regular | 1 | karaoke bar |
| karaoke bar | request collector | 1 | radio station |
| laundromat | wash-and-fold clerk | 1 | laundromat |
| laundromat | stain helper | 1 | laundromat |
| laundromat | machine repairer | 1 | hardware store |
| laundromat | bulk washer | 1 | laundromat |
| laundromat | dryer watcher | 1 | laundromat |
| lecture hall | course lecturer | 1 | lecture hall |
| lecture hall | teaching assistant | 1 | lecture hall |
| lecture hall | guest speaker | 1 | lecture hall |
| lecture hall | thesis presenter | 1 | lecture hall |
| lecture hall | seminar moderator | 1 | lecture hall |
| lecture hall | first-time attendee | 1 | lecture hall |
| mountain hut | hut keeper | 1 | mountain hut |
| mountain hut | soup cook | 1 | food truck rally |
| nature reserve | habitat ranger | 1 | nature reserve |
| nature reserve | bird bander | 1 | nature reserve |
| nature reserve | wildlife tracker | 1 | nature reserve |
| nature reserve | nest surveyor | 1 | nature reserve |
| nature reserve | burn crew member | 1 | nature reserve |
| night market | incense seller | 1 | night market |
| night market | late shopper | 1 | night market |
| night market | delivery rider | 1 | post office |
| opera house | pit violinist | 1 | opera house |
| opera house | language coach | 1 | lecture hall |
| overnight bus | reclining sleeper | 1 | overnight bus |
| overnight bus | relief driver | 1 | overnight bus |
| passport office | first-time applicant | 1 | passport office |
| passport office | renewal applicant | 1 | passport office |
| passport office | document examiner | 1 | passport office |
| passport office | biometric clerk | 1 | passport office |
| passport office | fraud reviewer | 1 | passport office |
| photo studio | headshot photographer | 1 | photo studio |
| photo studio | retoucher | 1 | photo studio |
| photo studio | product model | 1 | photo studio |
| planetarium | dome operator | 1 | planetarium |
| planetarium | telescope technician | 1 | planetarium |
| planetarium | meteorite curator | 1 | planetarium |
| post office | letter carrier | 1 | post office |
| post office | box renter | 1 | post office |
| post office | parcel sender | 1 | post office |
| post office | bulk mailer | 1 | post office |
| post office | stamp collector | 1 | post office |
| post office | parcel recipient | 1 | post office |
| radio station | call screener | 1 | radio station |
| radio station | music programmer | 1 | radio station |
| recording studio | mix engineer | 1 | recording studio |
| recording studio | tracking drummer | 1 | recording studio |
| recording studio | session producer | 1 | recording studio |
| recording studio | voice actor | 1 | recording studio |
| roller rink | derby skater | 1 | roller rink |
| sauna | whisk therapist | 1 | sauna |
| sauna | aroma keeper | 1 | sauna |
| sauna | heat-room host | 1 | sauna |
| ski lodge | ski instructor | 1 | ski lodge |
| ski lodge | boot fitter | 1 | ski lodge |
| street festival | neighborhood host | 1 | street festival |
| swimming pool | lane swimmer | 1 | swimming pool |
| swimming pool | diving coach | 1 | swimming pool |
| swimming pool | deck cleaner | 1 | ferry |
| tv newsroom | evening anchor | 1 | tv newsroom |
| tv newsroom | assignment editor | 1 | tv newsroom |
| tv newsroom | teleprompter operator | 1 | tv newsroom |
| tv newsroom | graphics producer | 1 | tv newsroom |
| vet clinic | exam room helper | 1 | dentist office |
| vet clinic | pet owner | 1 | vet clinic |
| vet clinic | kennel caretaker | 1 | vet clinic |
| video arcade | claw regular | 1 | video arcade |
| video arcade | score hunter | 1 | video arcade |
| video arcade | card reload helper | 1 | video arcade |
| water park | slide dispatcher | 1 | water park |
| water park | tube handler | 1 | water park |
| water park | wave operator | 1 | water park |
| water park | ride mechanic | 1 | county fair |

## Flagged generic by the generator, but fit fewer than 5 places (41)

| Place | Title | Fits | Places it fits |
|---|---|---|---|
| airport lounge | business traveler | 2 | airport lounge, overnight bus |
| airport lounge | night traveler | 1 | overnight bus |
| aquarium | gift shop cashier | 4 | aquarium, botanical garden, butterfly house, planetarium |
| bowling alley | birthday parent | 0 | (none) |
| cable car | window photographer | 1 | photo studio |
| dentist office | anxious patient | 1 | dentist office |
| ferry | commuter | 4 | airport lounge, cable car, ferry, overnight bus |
| food truck rally | local blogger | 4 | county fair, food truck rally, night market, street festival |
| hair salon | shop manager | 1 | hardware store |
| hardware store | weekend fixer | 1 | hardware store |
| hardware store | stock receiver | 1 | hardware store |
| hardware store | regular contractor | 1 | hardware store |
| hot spring | towel runner | 4 | hot spring, sauna, swimming pool, water park |
| ice fishing camp | overnight guest | 2 | mountain hut, ski lodge |
| ice rink | birthday parent | 0 | (none) |
| lecture hall | first-time attendee | 1 | lecture hall |
| lecture hall | note taker | 4 | lecture hall, radio station, recording studio, tv newsroom |
| lecture hall | latecomer | 4 | cinema, lecture hall, opera house, planetarium |
| mountain hut | overnight guest | 2 | mountain hut, ski lodge |
| mountain hut | bunk neighbor | 4 | ice fishing camp, mountain hut, overnight bus, ski lodge |
| night market | skewer griller | 3 | food truck rally, night market, street festival |
| night market | late shopper | 1 | night market |
| night market | delivery rider | 1 | post office |
| opera house | usher | 2 | cinema, opera house |
| overnight bus | late traveler | 2 | airport lounge, overnight bus |
| overnight bus | seatmate | 3 | cinema, ferry, overnight bus |
| passport office | first-time applicant | 1 | passport office |
| passport office | renewal applicant | 1 | passport office |
| post office | parcel recipient | 1 | post office |
| radio station | interview guest | 3 | radio station, recording studio, tv newsroom |
| radio station | computer technician | 4 | hardware store, radio station, recording studio, tv newsroom |
| recording studio | voice actor | 1 | recording studio |
| roller rink | birthday parent | 0 | (none) |
| sauna | towel runner | 4 | hot spring, sauna, swimming pool, water park |
| ski lodge | weekend guest | 2 | mountain hut, ski lodge |
| street festival | craft seller | 3 | county fair, night market, street festival |
| swimming pool | deck cleaner | 1 | ferry |
| tv newsroom | camera operator | 3 | cinema, photo studio, tv newsroom |
| tv newsroom | guest interviewee | 3 | radio station, recording studio, tv newsroom |
| vet clinic | pet owner | 1 | vet clinic |
| water park | locker attendant | 4 | ice rink, sauna, ski lodge, swimming pool |

## Not flagged generic, but fit 5 or more places (19)

| Place | Title | Fits | Places it fits |
|---|---|---|---|
| aquarium | water chemist | 5 | aquarium, hot spring, ice fishing camp, swimming pool, water park |
| cable car | wind monitor | 5 | cable car, ice fishing camp, mountain hut, nature reserve, ski lodge |
| car wash | membership seller | 6 | aquarium, botanical garden, cinema, planetarium, swimming pool, water park |
| car wash | maintenance mechanic | 18 | aquarium, botanical garden, bowling alley, butterfly house, cable car, car wash, cinema, county fair, ferry, hot spring, ice rink, laundromat, opera house, roller rink, sauna, ski lodge, swimming pool, water park |
| hot spring | temperature tester | 7 | aquarium, butterfly house, hot spring, ice rink, sauna, swimming pool, water park |
| karaoke bar | microphone runner | 7 | county fair, karaoke bar, lecture hall, radio station, recording studio, street festival, tv newsroom |
| lecture hall | microphone runner | 7 | county fair, karaoke bar, lecture hall, radio station, recording studio, street festival, tv newsroom |
| mountain hut | map reader | 6 | cable car, ferry, mountain hut, nature reserve, overnight bus, ski lodge |
| mountain hut | weather watcher | 11 | airport lounge, botanical garden, cable car, county fair, ferry, ice fishing camp, lecture hall, mountain hut, nature reserve, ski lodge, tv newsroom |
| overnight bus | snack runner | 15 | airport lounge, bowling alley, cinema, county fair, ferry, food truck rally, ice rink, karaoke bar, night market, opera house, roller rink, street festival, swimming pool, video arcade, water park |
| post office | counter clerk | 7 | bowling alley, car wash, cinema, food truck rally, hardware store, passport office, post office |
| recording studio | guitar player | 5 | karaoke bar, opera house, radio station, recording studio, street festival |
| recording studio | microphone tech | 5 | karaoke bar, opera house, radio station, recording studio, tv newsroom |
| roller rink | lesson coach | 5 | ice rink, lecture hall, roller rink, ski lodge, swimming pool |
| swimming pool | birthday chaperone | 7 | bowling alley, cinema, ice rink, roller rink, swimming pool, video arcade, water park |
| tv newsroom | field reporter | 6 | county fair, food truck rally, night market, radio station, street festival, tv newsroom |
| vet clinic | animal doctor | 6 | aquarium, butterfly house, county fair, nature reserve, vet clinic, water park |
| vet clinic | sample technician | 5 | aquarium, hot spring, nature reserve, swimming pool, vet clinic |
| video arcade | machine fixer | 8 | bowling alley, cable car, car wash, ice rink, laundromat, roller rink, video arcade, water park |

## The judge didn't list the role's own place (64)

| Place | Title | Fits | Places it fits |
|---|---|---|---|
| airport lounge | family chaperone | 19 | aquarium, botanical garden, bowling alley, butterfly house, cable car, cinema, county fair, ferry, food truck rally, hot spring, ice rink, nature reserve, night market, planetarium, roller rink, street festival, swimming pool, video arcade, water park |
| airport lounge | night traveler | 1 | overnight bus |
| airport lounge | shower attendant | 3 | hot spring, sauna, swimming pool |
| bowling alley | oil technician | 0 | (none) |
| bowling alley | practice coach | 3 | ice rink, roller rink, swimming pool |
| bowling alley | birthday parent | 0 | (none) |
| butterfly house | plant tender | 1 | botanical garden |
| butterfly house | climate monitor | 3 | aquarium, botanical garden, nature reserve |
| butterfly house | floor cleaner | 32 | airport lounge, aquarium, bowling alley, cinema, county fair, dentist office, ferry, food truck rally, hair salon, hardware store, ice rink, karaoke bar, laundromat, lecture hall, night market, opera house, overnight bus, passport office, photo studio, planetarium, post office, radio station, recording studio, roller rink, sauna, ski lodge, street festival, swimming pool, tv newsroom, vet clinic, video arcade, water park |
| cable car | line operator | 0 | (none) |
| cable car | cabin attendant | 1 | ferry |
| cable car | boarding host | 2 | ferry, overnight bus |
| cable car | summit guide | 2 | mountain hut, ski lodge |
| cable car | window photographer | 1 | photo studio |
| cable car | night cleaner | 24 | aquarium, bowling alley, cinema, dentist office, hair salon, hardware store, ice rink, karaoke bar, laundromat, lecture hall, opera house, passport office, planetarium, post office, radio station, recording studio, roller rink, sauna, ski lodge, swimming pool, tv newsroom, vet clinic, video arcade, water park |
| car wash | tunnel attendant | 1 | aquarium |
| car wash | membership seller | 6 | aquarium, botanical garden, cinema, planetarium, swimming pool, water park |
| car wash | chemical technician | 3 | aquarium, swimming pool, water park |
| car wash | night cleaner | 24 | aquarium, bowling alley, cinema, dentist office, hair salon, hardware store, ice rink, karaoke bar, laundromat, lecture hall, opera house, passport office, planetarium, post office, radio station, recording studio, roller rink, sauna, ski lodge, swimming pool, tv newsroom, vet clinic, video arcade, water park |
| dentist office | examining doctor | 0 | (none) |
| food truck rally | power wrangler | 4 | opera house, photo studio, recording studio, tv newsroom |
| food truck rally | propane checker | 1 | hardware store |
| food truck rally | parent chaperone | 14 | aquarium, botanical garden, bowling alley, butterfly house, cinema, county fair, ice rink, nature reserve, planetarium, roller rink, street festival, swimming pool, video arcade, water park |
| hair salon | extension specialist | 1 | lecture hall |
| hair salon | shop manager | 1 | hardware store |
| hardware store | garden advisor | 1 | botanical garden |
| hot spring | mineral guide | 1 | nature reserve |
| hot spring | source keeper | 2 | radio station, tv newsroom |
| ice fishing camp | minnow keeper | 1 | aquarium |
| ice fishing camp | family chaperone | 19 | aquarium, botanical garden, bowling alley, butterfly house, cable car, cinema, county fair, ferry, food truck rally, hot spring, ice rink, nature reserve, night market, planetarium, roller rink, street festival, swimming pool, video arcade, water park |
| ice fishing camp | overnight guest | 2 | mountain hut, ski lodge |
| ice rink | birthday parent | 0 | (none) |
| karaoke bar | request collector | 1 | radio station |
| laundromat | machine repairer | 1 | hardware store |
| laundromat | parent with kids | 19 | aquarium, botanical garden, bowling alley, butterfly house, cinema, county fair, ferry, food truck rally, ice rink, karaoke bar, lecture hall, nature reserve, night market, planetarium, roller rink, swimming pool, tv newsroom, video arcade, water park |
| lecture hall | room cleaner | 9 | airport lounge, cinema, ferry, hair salon, hot spring, mountain hut, overnight bus, sauna, ski lodge |
| mountain hut | soup cook | 1 | food truck rally |
| night market | tea pourer | 0 | (none) |
| night market | delivery rider | 1 | post office |
| opera house | language coach | 1 | lecture hall |
| overnight bus | window watcher | 0 | (none) |
| overnight bus | snack runner | 15 | airport lounge, bowling alley, cinema, county fair, ferry, food truck rally, ice rink, karaoke bar, night market, opera house, roller rink, street festival, swimming pool, video arcade, water park |
| overnight bus | night cleaner | 24 | aquarium, bowling alley, cinema, dentist office, hair salon, hardware store, ice rink, karaoke bar, laundromat, lecture hall, opera house, passport office, planetarium, post office, radio station, recording studio, roller rink, sauna, ski lodge, swimming pool, tv newsroom, vet clinic, video arcade, water park |
| overnight bus | anxious parent | 13 | aquarium, bowling alley, butterfly house, cinema, county fair, dentist office, ferry, ice rink, planetarium, roller rink, swimming pool, video arcade, water park |
| passport office | waiting parent | 5 | dentist office, hair salon, ice rink, roller rink, swimming pool |
| photo studio | print finisher | 0 | (none) |
| photo studio | new parent | 0 | (none) |
| photo studio | cleaner | 35 | airport lounge, aquarium, bowling alley, butterfly house, car wash, cinema, county fair, dentist office, ferry, food truck rally, hair salon, hardware store, hot spring, ice rink, karaoke bar, laundromat, lecture hall, mountain hut, night market, opera house, overnight bus, passport office, planetarium, post office, radio station, recording studio, roller rink, sauna, ski lodge, street festival, swimming pool, tv newsroom, vet clinic, video arcade, water park |
| planetarium | star presenter | 2 | radio station, tv newsroom |
| recording studio | first-time visitor | 37 | airport lounge, aquarium, botanical garden, bowling alley, butterfly house, cable car, car wash, cinema, county fair, dentist office, ferry, food truck rally, hair salon, hardware store, hot spring, ice fishing camp, ice rink, karaoke bar, laundromat, lecture hall, mountain hut, nature reserve, night market, opera house, overnight bus, passport office, photo studio, planetarium, post office, roller rink, sauna, ski lodge, street festival, swimming pool, vet clinic, video arcade, water park |
| recording studio | front desk host | 19 | airport lounge, aquarium, bowling alley, butterfly house, cinema, dentist office, hair salon, hot spring, ice rink, karaoke bar, mountain hut, opera house, photo studio, planetarium, sauna, ski lodge, swimming pool, vet clinic, water park |
| roller rink | speed regular | 0 | (none) |
| roller rink | birthday parent | 0 | (none) |
| roller rink | music operator | 4 | karaoke bar, opera house, radio station, recording studio |
| sauna | stove tender | 2 | ice fishing camp, mountain hut |
| ski lodge | parent with kids | 19 | aquarium, botanical garden, bowling alley, butterfly house, cinema, county fair, ferry, food truck rally, ice rink, karaoke bar, lecture hall, nature reserve, night market, planetarium, roller rink, swimming pool, tv newsroom, video arcade, water park |
| swimming pool | deck cleaner | 1 | ferry |
| tv newsroom | gallery director | 0 | (none) |
| vet clinic | exam room helper | 1 | dentist office |
| vet clinic | medicine runner | 0 | (none) |
| vet clinic | imaging specialist | 4 | photo studio, radio station, recording studio, tv newsroom |
| video arcade | birthday guest | 6 | bowling alley, cinema, karaoke bar, roller rink, swimming pool, water park |
| water park | locker attendant | 4 | ice rink, sauna, ski lodge, swimming pool |
| water park | ride mechanic | 1 | county fair |

## Per place

| Place | Generic (bank) | Generic (audit, >= 5) | Fit only here |
|---|---|---|---|
| airport lounge | 4 | 2 | 3 |
| aquarium | 4 | 4 | 4 |
| botanical garden | 4 | 4 | 5 |
| bowling alley | 4 | 3 | 3 |
| butterfly house | 5 | 5 | 3 |
| cable car | 4 | 4 | 0 |
| car wash | 4 | 6 | 2 |
| cinema | 4 | 4 | 3 |
| county fair | 4 | 4 | 5 |
| dentist office | 4 | 3 | 5 |
| ferry | 4 | 3 | 4 |
| food truck rally | 4 | 3 | 3 |
| hair salon | 4 | 3 | 4 |
| hardware store | 4 | 1 | 8 |
| hot spring | 4 | 4 | 1 |
| ice fishing camp | 4 | 3 | 5 |
| ice rink | 4 | 3 | 4 |
| karaoke bar | 4 | 5 | 2 |
| laundromat | 4 | 4 | 4 |
| lecture hall | 4 | 2 | 6 |
| mountain hut | 3 | 3 | 1 |
| nature reserve | 4 | 4 | 5 |
| night market | 4 | 1 | 2 |
| opera house | 4 | 3 | 1 |
| overnight bus | 4 | 3 | 2 |
| passport office | 4 | 2 | 5 |
| photo studio | 3 | 3 | 3 |
| planetarium | 4 | 4 | 3 |
| post office | 4 | 4 | 6 |
| radio station | 4 | 2 | 2 |
| recording studio | 4 | 5 | 4 |
| roller rink | 4 | 4 | 1 |
| sauna | 5 | 4 | 3 |
| ski lodge | 3 | 2 | 2 |
| street festival | 4 | 3 | 1 |
| swimming pool | 4 | 4 | 2 |
| tv newsroom | 4 | 3 | 4 |
| vet clinic | 4 | 5 | 2 |
| video arcade | 4 | 5 | 3 |
| water park | 4 | 3 | 3 |
