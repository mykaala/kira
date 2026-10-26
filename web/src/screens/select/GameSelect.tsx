import { Button } from '../../components/Button';
import { Portrait } from '../../components/Portrait';
import { SiteHeader } from '../../components/SiteHeader';
import type { CharacterId } from '../../cast';
import { useSpyConfig } from '../../spy/useSpyConfig';
import { ArrowIcon, HourglassIcon, InfoIcon } from '../../components/Icons';
import { GAMES } from './games';
import styles from './GameSelect.module.css';

function Bluff({ level }: { level: number }) {
	return (
		<span aria-label={`Bluff level ${level} of 3`}>
			Bluff{' '}
			{[1, 2, 3].map((i) => (
				<span key={i} style={{ color: i <= level ? 'var(--text)' : 'var(--line)' }}>
					●
				</span>
			))}
		</span>
	);
}

/** Info and Play side by side. Hovering or focusing Info swaps their widths: Info grows to read
 * "How to Play" and Play shrinks to its arrow. Touch screens never hover, so a tap on Info just goes. */
function CardActions({
	game,
	title,
	cta,
	playable,
	disabled,
	onPlay
}: {
	game: string;
	title: string;
	cta: string;
	playable: boolean;
	disabled: boolean;
	onPlay: () => void;
}) {
	return (
		<div className={styles.actions}>
			<a href={`#/how/${game}`} className={styles.info} aria-label={`How to play ${title}`}>
				<InfoIcon />
				<span className={styles.infoLabel} aria-hidden='true'>
					How to Play
				</span>
			</a>
			<Button
				variant={playable ? 'lantern' : 'surface'}
				size='large'
				className={styles.play}
				disabled={disabled}
				onClick={onPlay}
				aria-label={cta}
			>
				<span className={styles.playLabel}>{cta}</span>
				{playable ? <ArrowIcon /> : <HourglassIcon />}
			</Button>
		</div>
	);
}

/** "Who's lying tonight?": pick a game, or pick up an unfinished one. */
export function GameSelect({
	lastGame,
	lastCast,
	onPick,
	onContinue,
	lastSpyGame,
	onContinueSpy
}: {
	lastGame: string | null;
	lastSpyGame?: string | null;
	onContinueSpy?: (gameId: string) => void;
	lastCast: CharacterId[];
	onPick: (game: string) => void;
	onContinue: (gameId: string) => void;
}) {
	const spyTitle = useSpyConfig()?.title ?? '';
	return (
		<div className='lantern-page'>
			<div className={styles.page}>
				<SiteHeader current='play' />
				<div className={styles.hero}>
					<div>
						<span className={`meta ${styles.eyebrow}`}>
							Three games of trust and betrayal. Every other seat is an agent with a temper, a memory, and something to
							hide.
						</span>
						<h1 className={styles.title}>Pick your table...</h1>
					</div>
				</div>

				<div className={styles.grid}>
					{GAMES.map((g) => {
						const title = g.id === 'out-of-place' ? spyTitle : g.title;
						return (
							<article key={g.id} className={`${styles.card} ${g.playable ? styles.featured : ''}`}>
								<div className={styles.art} style={{ background: g.background }}>
									<svg viewBox='0 0 400 220' preserveAspectRatio='xMidYMax slice' aria-hidden='true'>
										{g.scene}
									</svg>
									{g.playable ? (
										<span className={styles.badge}>{g.badge ?? 'MOST PLAYED'}</span>
									) : (
										<span className={`${styles.badge} ${styles.soon}`}>SOON</span>
									)}
								</div>
								<div className={styles.body}>
									<h2 className={styles.cardTitle}>{title}</h2>
									<p className={styles.lede}>{g.pitch}</p>
									<div className={`meta ${styles.chips}`}>
										{g.chips.map((c) => (
											<span key={c} className={styles.chip}>
												{c}
											</span>
										))}
										<span className={styles.chip}>
											<Bluff level={g.bluff} />
										</span>
									</div>
									<CardActions
										game={g.id}
										title={title}
										cta={g.cta}
										playable={g.playable}
										disabled={!g.playable || (g.id === 'out-of-place' && !spyTitle)}
										onPlay={() => onPick(g.id)}
									/>
								</div>
							</article>
						);
					})}
				</div>

				{lastGame && (
					<div className={styles.continue}>
						<div className={styles.who}>
							{lastCast.length > 0 && (
								<span className={styles.faces}>
									{lastCast.slice(0, 3).map((c) => (
										<Portrait key={c} character={c} size={48} />
									))}
								</span>
							)}
							<div className={styles.continueText}>
								<strong className={styles.continueTitle}>Unfinished game · Mafia</strong>
								<span className={styles.muted}>The table is still waiting for you.</span>
							</div>
						</div>
						<Button variant='ghost' onClick={() => onContinue(lastGame)}>
							Pick up where you left off
						</Button>
					</div>
				)}
				{lastSpyGame && onContinueSpy && (
					<div className={styles.continue}>
						<div className={styles.continueText}>
							<strong className={styles.continueTitle}>Unfinished game · {spyTitle || '…'}</strong>
							<span className={styles.muted}>The question round is waiting for you.</span>
						</div>
						<Button variant='ghost' onClick={() => onContinueSpy(lastSpyGame)}>
							Pick up where you left off
						</Button>
					</div>
				)}
			</div>
		</div>
	);
}
