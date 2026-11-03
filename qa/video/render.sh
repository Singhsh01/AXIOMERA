#!/bin/bash
set -e
F=/tmp/claude-0/frames; D=(2.5 2.5 2.5 2.5 2.5 2.5); X=0.4; Z=0.035
ENC="-c:v libx264 -crf 18 -preset veryfast -pix_fmt yuv420p -r 30"
for i in 1 2 3 4 5 6; do
  d=${D[$((i-1))]}; n=$(python3 -c "print(round($d*30))")
  zp="zoompan=z='1+$Z*on/($n-1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=$n:s=1280x800:fps=30,setsar=1"
  if [ $i -eq 1 ]; then
    ffmpeg -y -loglevel error -framerate 30 -i $F/s1.jpg -vf "$zp,fade=t=in:st=0:d=0.35:color=white,format=yuv420p" $ENC tmp_s1.mp4
  else
    p=$((i-1)); xn=$(python3 -c "print(round($X*30))")
    ffmpeg -y -loglevel error -framerate 30 -i $F/s$p.jpg -framerate 30 -i $F/s$i.jpg -filter_complex \
      "[0]zoompan=z='1+$Z':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=$xn:s=1280x800:fps=30,setsar=1,format=yuv420p[a];[1]$zp,format=yuv420p[b];[a][b]xfade=transition=fade:duration=$X:offset=0,trim=duration=$d$( [ $i -eq 6 ] && echo ",fade=t=out:st=$(python3 -c "print($d-0.35)"):d=0.35:color=white" )" \
      $ENC tmp_s$i.mp4
  fi
  mv tmp_s$i.mp4 s$i.mp4
done
printf "file 's%d.mp4'\n" 1 2 3 4 5 6 > list.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i list.txt -c copy -movflags +faststart tmp_out.mp4 && mv tmp_out.mp4 axiomera-use-case.mp4
ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate,nb_frames -of compact axiomera-use-case.mp4
