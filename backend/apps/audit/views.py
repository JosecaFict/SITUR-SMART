from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import AuditLog





class AuditLogListView(APIView):

    permission_classes = (
        IsAuthenticated,
    )



    def get(
        self,
        request
    ):


        logs = (

            AuditLog.objects

            .select_related(
                "user",
                "tenant",
            )

            .all()

            .order_by(
                "-created_at"
            )[:100]

        )



        data = []



        for log in logs:



            data.append(

                {

                    "id":
                        log.id,



                    "usuario":

                        {

                            "id":
                                log.user_id,


                            "nombre":

                                (

                                    f"{log.user.first_names} {log.user.last_names}"

                                    if log.user

                                    else "Sistema"

                                ),



                            "correo":

                                (

                                    log.user.email

                                    if log.user

                                    else None

                                ),

                        },





                    "empresa":

                        (

                            log.tenant.trade_name

                            if log.tenant

                            else None

                        ),





                    "accion":

                        log.action,





                    "entidad":

                        log.entity,





                    "entidad_id":

                        log.entity_id,





                    "datos_anteriores":

                        log.previous_data,





                    "datos_nuevos":

                        log.new_data,





                    "ip":

                        log.ip,





                    "user_agent":

                        log.user_agent,





                    "request_id":

                        log.request_id,





                    "fecha":

                        log.created_at,

                }

            )



        return Response(
            data
        )